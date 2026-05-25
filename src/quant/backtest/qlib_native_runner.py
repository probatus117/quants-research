"""Qlib native Alpha158/LightGBM/backtest workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.backtest.metrics import calculate_metrics
from src.quant.backtest.pandas_runner import BacktestResult
from src.quant.config import load_yaml_config
from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.data.qlib_bin_writer import check_qlib_data_capability, init_qlib_provider


@dataclass(frozen=True)
class QlibNativeCapability:
    """Layered runtime availability for the native Qlib pathway."""

    qlib_data_available: bool
    qlib_model_available: bool
    qlib_backtest_available: bool
    skip_reason: str | None = None
    data_skip_reason: str | None = None
    model_skip_reason: str | None = None
    backtest_skip_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.qlib_data_available and self.qlib_model_available and self.qlib_backtest_available

    def to_dict(self) -> dict[str, Any]:
        return {
            "qlib_data_available": self.qlib_data_available,
            "qlib_model_available": self.qlib_model_available,
            "qlib_backtest_available": self.qlib_backtest_available,
            "skip_reason": self.skip_reason,
            "data_skip_reason": self.data_skip_reason,
            "model_skip_reason": self.model_skip_reason,
            "backtest_skip_reason": self.backtest_skip_reason,
        }


@dataclass(frozen=True)
class QlibNativeConfig:
    """Configuration for a native Qlib research run."""

    market: str = "cn"
    provider_uri: dict[str, str] | None = None
    qlib_bin_dir: str | Path = "data/quant/qlib_bin"
    universe: str | None = None
    dataset_config: dict[str, Any] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)
    backtest_config: dict[str, Any] = field(default_factory=dict)
    data_version: dict[str, Any] | None = None

    def resolved_provider_uri(self) -> dict[str, str]:
        if self.provider_uri:
            return self.provider_uri
        return {"day": str(Path(self.qlib_bin_dir) / normalize_market(self.market))}


@dataclass(frozen=True)
class QlibNativeResult:
    """Audit payload for native Qlib execution or skipped execution."""

    available: bool
    fallback_used: bool
    skip_reason: str | None
    capability: QlibNativeCapability
    artifacts: dict[str, str]
    metrics: dict[str, Any]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "qlib_native_runner",
            "available": self.available,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "capability": self.capability.to_dict(),
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }


def _first_reason(*reasons: str | None) -> str | None:
    return next((reason for reason in reasons if reason), None)


def check_qlib_native_capability(require_model: bool = True, require_backtest: bool = True) -> QlibNativeCapability:
    """Check data/model/backtest layers independently."""

    data_cap = check_qlib_data_capability()
    model_available = True
    model_reason = None
    backtest_available = True
    backtest_reason = None

    if require_model:
        try:
            import lightgbm  # noqa: F401
            from qlib.contrib.model.gbdt import LGBModel  # noqa: F401
        except Exception as exc:  # pragma: no cover - depends on optional dynamic libs.
            model_available = False
            model_reason = f"Qlib model layer unavailable: {type(exc).__name__}: {exc}"

    if require_backtest:
        try:
            from qlib.backtest import backtest  # noqa: F401
            from qlib.backtest.executor import SimulatorExecutor  # noqa: F401
            from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy  # noqa: F401
            from qlib.workflow.record_temp import PortAnaRecord, SignalRecord  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment-specific.
            backtest_available = False
            backtest_reason = f"Qlib backtest layer unavailable: {type(exc).__name__}: {exc}"

    skip_reason = _first_reason(
        data_cap.skip_reason if not data_cap.available else None,
        model_reason if require_model and not model_available else None,
        backtest_reason if require_backtest and not backtest_available else None,
    )
    return QlibNativeCapability(
        qlib_data_available=data_cap.available,
        qlib_model_available=model_available,
        qlib_backtest_available=backtest_available,
        skip_reason=skip_reason,
        data_skip_reason=data_cap.skip_reason if not data_cap.available else None,
        model_skip_reason=model_reason,
        backtest_skip_reason=backtest_reason,
    )


def _config_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key, {})
    return dict(value) if isinstance(value, dict) else {}


def load_qlib_native_config(
    market: str = "cn",
    qlib_bin_dir: str | Path = "data/quant/qlib_bin",
    dataset_config_path: str | Path = "config/qlib/dataset.yaml",
    model_config_path: str | Path = "config/qlib/model.yaml",
    backtest_config_path: str | Path = "config/qlib/backtest.yaml",
) -> QlibNativeConfig:
    """Load the three Qlib YAML config files with market overrides."""

    normalized = normalize_market(market)
    dataset_yaml = load_yaml_config(dataset_config_path)
    model_yaml = load_yaml_config(model_config_path)
    backtest_yaml = load_yaml_config(backtest_config_path)
    dataset_config = {**_config_section(dataset_yaml, "dataset"), **_config_section(_config_section(dataset_yaml, "markets"), normalized)}
    model_config = {**_config_section(model_yaml, "model"), **_config_section(_config_section(model_yaml, "markets"), normalized)}
    backtest_config = {**_config_section(backtest_yaml, "backtest"), **_config_section(_config_section(backtest_yaml, "markets"), normalized)}
    return QlibNativeConfig(
        market=normalized,
        qlib_bin_dir=qlib_bin_dir,
        universe=str(dataset_config.get("market", normalized)),
        dataset_config=dataset_config,
        model_config=model_config,
        backtest_config=backtest_config,
    )


def train_qlib_model(
    provider_uri: dict[str, str],
    market: str,
    model_config: dict[str, Any],
    dataset_config: dict[str, Any],
) -> tuple[Any, Any]:
    """Train a Qlib Alpha158 + LightGBM model and return model/dataset."""

    output_dir = provider_uri.get("day") or next(iter(provider_uri.values()))
    init_qlib_provider(output_dir, market)
    from qlib.contrib.data.handler import Alpha158
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.data.dataset import DatasetH

    segments = dict(dataset_config.get("segments", {}))
    if not segments:
        segments = {
            "train": (dataset_config.get("train_start_time"), dataset_config.get("train_end_time")),
            "valid": (dataset_config.get("valid_start_time"), dataset_config.get("valid_end_time")),
            "test": (dataset_config.get("test_start_time"), dataset_config.get("test_end_time")),
        }
    handler = Alpha158(
        instruments=dataset_config.get("market", market),
        start_time=dataset_config.get("start_time"),
        end_time=dataset_config.get("end_time"),
        fit_start_time=segments.get("train", (None, None))[0],
        fit_end_time=segments.get("train", (None, None))[1],
        freq=dataset_config.get("freq", "day"),
        label=dataset_config.get("label", ["Ref($close, -20) / $close - 1"]),
    )
    dataset = DatasetH(handler=handler, segments=segments)
    params = dict(model_config.get("params", model_config))
    model = LGBModel(**params)
    model.fit(dataset)
    return model, dataset


def run_qlib_native_backtest(model: Any, dataset: Any, backtest_config: dict[str, Any], market: str) -> tuple[Any, Any, pd.Series | pd.DataFrame]:
    """Run Qlib TopkDropoutStrategy + SimulatorExecutor against model predictions."""

    from qlib.backtest import backtest
    from qlib.backtest.executor import SimulatorExecutor
    from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy

    prediction = model.predict(dataset, segment=backtest_config.get("segment", "test"))
    signal = prediction.iloc[:, 0] if isinstance(prediction, pd.DataFrame) else prediction
    start_time, end_time = _prediction_date_span(signal)
    strategy = TopkDropoutStrategy(
        signal=signal,
        topk=int(backtest_config.get("topk", 10)),
        n_drop=int(backtest_config.get("n_drop", 2)),
    )
    executor = SimulatorExecutor(
        time_per_step=str(backtest_config.get("time_per_step", "day")),
        generate_portfolio_metrics=True,
    )
    market_cfg = get_market_config(market)
    exchange_kwargs = {
        "freq": "day",
        "limit_threshold": backtest_config.get("limit_threshold"),
        "deal_price": backtest_config.get("deal_price", "close"),
        "open_cost": float(backtest_config.get("open_cost", market_cfg.buy_cost)),
        "close_cost": float(backtest_config.get("close_cost", market_cfg.sell_cost)),
        "min_cost": float(backtest_config.get("min_cost", market_cfg.min_cost)),
        "trade_unit": int(backtest_config.get("trade_unit", 100 if market == "cn" else 1)),
    }
    portfolio_metric, indicator_metric = backtest(
        start_time=start_time,
        end_time=end_time,
        strategy=strategy,
        executor=executor,
        benchmark=str(backtest_config.get("benchmark", market_cfg.benchmark_symbol)),
        account=float(backtest_config.get("initial_capital", 1_000_000.0)),
        exchange_kwargs=exchange_kwargs,
    )
    return portfolio_metric, indicator_metric, signal


def _prediction_date_span(prediction: pd.Series | pd.DataFrame) -> tuple[str, str]:
    index = prediction.index
    if isinstance(index, pd.MultiIndex):
        dates = pd.to_datetime(index.get_level_values(0))
    else:
        dates = pd.to_datetime(index)
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def qlib_predictions_to_signal(prediction: pd.Series | pd.DataFrame, market: str = "cn") -> pd.DataFrame:
    """Convert Qlib prediction output to the project signal schema."""

    if isinstance(prediction, pd.DataFrame):
        score_col = "score" if "score" in prediction.columns else prediction.columns[0]
        series = prediction[score_col]
    else:
        series = prediction
    if isinstance(series.index, pd.MultiIndex):
        frame = series.rename("score").reset_index()
        frame.columns = ["date", "symbol", "score"] + list(frame.columns[3:])
    else:
        frame = series.rename("score").reset_index()
        frame.columns = ["date", "score"]
        frame["symbol"] = "QLIB_SIGNAL"
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["market"] = normalize_market(market)
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    return frame[["date", "market", "symbol", "score"]].sort_values(["date", "score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)


def qlib_portfolio_to_backtest_result(
    portfolio_metric: Any,
    positions: pd.DataFrame | None = None,
    trades: pd.DataFrame | None = None,
    market: str = "cn",
) -> BacktestResult:
    """Convert Qlib portfolio artifacts into BacktestResult-compatible frames.

    Qlib backtest() returns PORT_METRIC = Dict[str, Tuple[DataFrame, Dict]].
    This function extracts the ``account`` column (total portfolio = cash + holdings).
    """

    if isinstance(portfolio_metric, dict):
        # Qlib native format: {'1day': (DataFrame, {})}
        for _freq, (pm_df, _meta) in portfolio_metric.items():
            if isinstance(pm_df, pd.DataFrame) and not pm_df.empty:
                portfolio_metric = pm_df
                break

    if isinstance(portfolio_metric, tuple):
        portfolio_metric = portfolio_metric[0]
    if isinstance(portfolio_metric, pd.Series):
        portfolio = portfolio_metric.rename("portfolio_value").reset_index()
    elif isinstance(portfolio_metric, pd.DataFrame):
        portfolio = portfolio_metric.reset_index() if portfolio_metric.index.name or not isinstance(portfolio_metric.index, pd.RangeIndex) else portfolio_metric.copy()
    else:
        portfolio = pd.DataFrame(columns=["date", "portfolio_value"])

    # Standardize date column
    if "date" not in portfolio.columns:
        index_name = portfolio.index.name
        first = portfolio.columns[0] if len(portfolio.columns) else "date"
        date_candidate = "datetime" if "datetime" in str(index_name).lower() else first
        portfolio = portfolio.rename(columns={date_candidate: "date"})

    # Use account (total cash+holdings) as portfolio_value, fallback to value
    if "portfolio_value" not in portfolio.columns:
        if "account" in portfolio.columns:
            portfolio = portfolio.rename(columns={"account": "portfolio_value"})
        elif "value" in portfolio.columns:
            portfolio = portfolio.rename(columns={"value": "portfolio_value"})

    if "portfolio_value" not in portfolio.columns:
        portfolio["portfolio_value"] = pd.NA

    # Preserve benchmark return and turnover for metrics
    if "bench" in portfolio.columns:
        # Qlib bench column is daily benchmark return series; cumulative to benchmark_value
        portfolio["benchmark_value"] = (1.0 + pd.to_numeric(portfolio["bench"], errors="coerce").fillna(0.0)).cumprod()
        # Scale benchmark to same initial capital for fair comparison
        if "portfolio_value" in portfolio.columns and not portfolio["portfolio_value"].isna().all():
            initial_pv = float(pd.to_numeric(portfolio["portfolio_value"], errors="coerce").iloc[0])
            if initial_pv > 0:
                portfolio["benchmark_value"] = portfolio["benchmark_value"] * initial_pv
    if "total_turnover" in portfolio.columns and "turnover" not in portfolio.columns:
        portfolio = portfolio.rename(columns={"total_turnover": "turnover"})
    if "turnover" not in portfolio.columns:
        portfolio["turnover"] = 0.0

    portfolio["date"] = pd.to_datetime(portfolio["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    portfolio["market"] = normalize_market(market)
    portfolio["daily_return"] = pd.to_numeric(portfolio["portfolio_value"], errors="coerce").pct_change().fillna(0.0)

    return BacktestResult(
        portfolio_value=portfolio,
        positions=positions if positions is not None else pd.DataFrame(),
        trades=trades if trades is not None else pd.DataFrame(),
    )


def write_qlib_native_summary(path: str | Path, result: QlibNativeResult, config: QlibNativeConfig) -> Path:
    """Write qlib_native_summary.json."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **result.to_metadata(),
        "data_version": config.data_version,
        "provider_uri": config.resolved_provider_uri(),
        "region_mapping": {normalize_market(config.market): "cn" if normalize_market(config.market) == "cn" else "us"},
        "dataset_segments": config.dataset_config.get("segments"),
        "model_params": config.model_config.get("params", config.model_config),
        "backtest_params": config.backtest_config,
    }
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return output


def run_qlib_native_workflow(
    config: QlibNativeConfig,
    output_dir: str | Path = "data/quant/qlib_native",
    enabled: bool = True,
) -> QlibNativeResult:
    """Run the native Qlib workflow or write an audited skip marker."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "qlib_native_summary.json"
    capability = check_qlib_native_capability(require_model=True, require_backtest=True)
    if not enabled or not capability.available:
        reason = "qlib native workflow disabled by caller" if not enabled else capability.skip_reason
        result = QlibNativeResult(
            available=False,
            fallback_used=True,
            skip_reason=reason,
            capability=capability,
            artifacts={"summary": str(summary_path)},
            metrics={},
        )
        write_qlib_native_summary(summary_path, result, config)
        return result

    try:
        model, dataset = train_qlib_model(config.resolved_provider_uri(), config.market, config.model_config, config.dataset_config)
        portfolio_metric, indicator_metric, prediction = run_qlib_native_backtest(model, dataset, config.backtest_config, config.market)
        signal = qlib_predictions_to_signal(prediction, config.market)
        backtest_result = qlib_portfolio_to_backtest_result(portfolio_metric, market=config.market)
        predictions_path = output / "predictions.csv"
        portfolio_path = output / "portfolio_value.csv"
        metrics_path = output / "portfolio_metrics.json"
        signal.to_csv(predictions_path, index=False)
        backtest_result.portfolio_value.to_csv(portfolio_path, index=False)
        metrics = calculate_metrics(backtest_result.portfolio_value) if not backtest_result.portfolio_value.empty else {}
        metrics_payload = {"metrics": metrics, "indicator_metric": str(indicator_metric)}
        metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=True, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        artifacts = {
            "predictions": str(predictions_path),
            "portfolio_value": str(portfolio_path),
            "portfolio_metrics": str(metrics_path),
            "summary": str(summary_path),
        }
        result = QlibNativeResult(
            available=True,
            fallback_used=False,
            skip_reason=None,
            capability=capability,
            artifacts=artifacts,
            metrics=metrics,
        )
    except Exception as exc:
        reason = f"qlib native workflow failed: {type(exc).__name__}: {exc}"
        degraded = QlibNativeCapability(
            qlib_data_available=capability.qlib_data_available,
            qlib_model_available=capability.qlib_model_available,
            qlib_backtest_available=capability.qlib_backtest_available,
            skip_reason=reason,
            data_skip_reason=capability.data_skip_reason,
            model_skip_reason=capability.model_skip_reason,
            backtest_skip_reason=capability.backtest_skip_reason,
        )
        result = QlibNativeResult(
            available=False,
            fallback_used=True,
            skip_reason=reason,
            capability=degraded,
            artifacts={"summary": str(summary_path)},
            metrics={},
        )
    write_qlib_native_summary(summary_path, result, config)
    return result
