"""Quant backtest CLI for pandas TopN backtests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.backtest.cost_model import CostConfig
from src.quant.backtest.metrics import calculate_metrics
from src.quant.backtest.pandas_runner import BacktestConfig, run_topn_backtest
from src.quant.backtest.qlib_runner import run_qlib_backtest, write_qlib_vs_pandas_comparison
from src.quant.backtest.signal_builder import (
    COMPOSITE_V1_WEIGHTS,
    SignalConfig,
    build_composite_signal,
    build_single_factor_signal,
    write_signal,
)
from src.quant.backtest.walk_forward import walk_forward_metrics
from src.quant.backtest.vectorbt_runner import run_vectorbt_grid
from src.quant.config import load_yaml_config
from src.quant.data.market_config import get_market_config
from src.quant.data.storage import read_parquet
from src.quant.reports.backtest_report import write_backtest_report
from src.quant.reports.charts import write_backtest_charts
from src.quant.reports.robustness_report import market_state_decomposition, write_robustness_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant backtest CLI")
    subparsers = parser.add_subparsers(dest="command")
    p_run = subparsers.add_parser("run", help="Run pandas TopN backtest")
    p_run.add_argument("--config", default="config/quant_backtest.yaml", help="Backtest config YAML")
    p_run.add_argument("--input-dir", default="data/quant", help="Quant data directory")
    p_run.add_argument("--output-dir", default="data/quant/backtest", help="Backtest output directory")
    p_run.add_argument("--signal", default=None, help="Signal name: composite_v1 or a single factor name")
    p_run.add_argument("--universe", default=None, help="Universe label")
    p_run.add_argument("--top-n", type=int, default=None, help="TopN holdings")
    p_run.add_argument("--initial-capital", type=float, default=None, help="Initial portfolio value")
    p_run.add_argument("--qlib", action="store_true", help="Also run optional Qlib adapter")
    p_run.add_argument("--vectorbt", action="store_true", help="Also run optional vectorbt parameter grid")
    p_run.add_argument("--robustness", action="store_true", help="Write Phase 7b robustness and sensitivity artifacts")
    p_run.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    return parser


def _backtest_config_from_yaml(path: str | Path) -> dict[str, Any]:
    config = load_yaml_config(path)
    return dict(config.get("backtest", {}))


def _cost_config(raw: dict[str, Any]) -> CostConfig:
    return CostConfig(
        market=str(raw.get("market", "cn")),
        buy_cost=float(raw.get("buy_cost", raw.get("buy_cost_rate", 0.0015))),
        sell_cost=float(raw.get("sell_cost", raw.get("sell_cost_rate", 0.0025))),
        min_cost=float(raw.get("min_cost", 5.0)),
    )


def _resolve_market_from_data(
    requested_market: str,
    requested_base_currency: str,
    requested_benchmark: str,
    daily_bar,
) -> tuple[str, str, str]:
    if "market" not in daily_bar.columns:
        return requested_market, requested_base_currency, requested_benchmark
    available = sorted(str(market) for market in daily_bar["market"].dropna().unique())
    if requested_market in available or len(available) != 1:
        return requested_market, requested_base_currency, requested_benchmark
    resolved_market = available[0]
    cfg = get_market_config(resolved_market)
    return resolved_market, cfg.currency, cfg.benchmark


def _build_signal(
    factor_values,
    signal_name: str,
    universe: str,
    factor_column: str,
):
    if signal_name == "composite_v1":
        return build_composite_signal(
            factor_values,
            SignalConfig(
                signal_name="composite_v1",
                factor_weights=dict(COMPOSITE_V1_WEIGHTS),
                factor_column=factor_column,
                universe=universe,
                min_factors=2,
            ),
        )
    return build_single_factor_signal(factor_values, signal_name, factor_column=factor_column, universe=universe)


def _cost_sensitivity(signal, daily_bar, config: BacktestConfig, costs: tuple[float, ...] = (0.0, 0.001, 0.002, 0.005)):
    rows = []
    for cost in costs:
        cfg = BacktestConfig(
            top_n=config.top_n,
            market=config.market,
            base_currency=config.base_currency,
            benchmark=config.benchmark,
            frequency=config.frequency,
            initial_capital=config.initial_capital,
            exclude_st=config.exclude_st,
            exclude_suspended=config.exclude_suspended,
            cost=CostConfig(market=config.market, buy_cost=cost, sell_cost=cost, min_cost=0),
            strategy=config.strategy,
        )
        metrics = calculate_metrics(run_topn_backtest(signal, daily_bar, cfg).portfolio_value)
        rows.append({"cost_bps": int(cost * 10000), **{key: metrics[key] for key in ("annual_return", "sharpe", "max_drawdown", "excess_return")}})
    return rows


def _topn_sensitivity(signal, daily_bar, config: BacktestConfig, topn_values: tuple[int, ...] | None = None):
    universe_size = int(signal["symbol"].nunique())
    candidates = topn_values or (min(5, universe_size), min(10, universe_size), min(20, universe_size), min(50, universe_size))
    rows = []
    for top_n in sorted({value for value in candidates if value > 0}):
        cfg = BacktestConfig(
            top_n=top_n,
            market=config.market,
            base_currency=config.base_currency,
            benchmark=config.benchmark,
            frequency=config.frequency,
            initial_capital=config.initial_capital,
            exclude_st=config.exclude_st,
            exclude_suspended=config.exclude_suspended,
            cost=config.cost,
            strategy=config.strategy,
        )
        metrics = calculate_metrics(run_topn_backtest(signal, daily_bar, cfg).portfolio_value)
        rows.append({"top_n": int(top_n), **{key: metrics[key] for key in ("annual_return", "sharpe", "max_drawdown", "excess_return")}})
    return rows


def run_backtest(
    config_path: str | Path = "config/quant_backtest.yaml",
    input_dir: str | Path = "data/quant",
    output_dir: str | Path = "data/quant/backtest",
    signal_name: str | None = None,
    universe: str | None = None,
    top_n: int | None = None,
    initial_capital: float | None = None,
    use_qlib: bool = False,
    use_vectorbt: bool = False,
    use_robustness: bool = False,
    write_charts: bool = True,
) -> dict[str, object]:
    raw_config = _backtest_config_from_yaml(config_path)
    resolved_signal = signal_name or str(raw_config.get("signal", "composite_v1"))
    resolved_universe = universe or str(raw_config.get("universe", "sample_a"))
    resolved_market = str(raw_config.get("market", "cn"))
    resolved_base_currency = str(raw_config.get("base_currency", "CNY"))
    resolved_benchmark = str(raw_config.get("benchmark", "equal_weight"))
    resolved_top_n = int(top_n if top_n is not None else raw_config.get("top_n", 10))
    resolved_initial = float(initial_capital if initial_capital is not None else raw_config.get("initial_capital", 1_000_000.0))
    factor_column = str(raw_config.get("factor_column", "zscore"))
    parquet_root = Path(input_dir) / "parquet"
    output_root = Path(output_dir) / resolved_signal
    output_root.mkdir(parents=True, exist_ok=True)

    factor_values = read_parquet("factor_value", root=parquet_root)
    daily_bar = read_parquet("daily_bar", root=parquet_root)
    resolved_market, resolved_base_currency, resolved_benchmark = _resolve_market_from_data(
        resolved_market,
        resolved_base_currency,
        resolved_benchmark,
        daily_bar,
    )
    signal = _build_signal(factor_values, resolved_signal, resolved_universe, factor_column)
    signal_path = write_signal(signal, parquet_root=output_root / "parquet")

    raw_config["market"] = resolved_market
    cost = _cost_config(raw_config)
    backtest_config = BacktestConfig(
        top_n=resolved_top_n,
        market=resolved_market,
        base_currency=resolved_base_currency,
        benchmark=resolved_benchmark,
        frequency=str(raw_config.get("frequency", "monthly")),
        initial_capital=resolved_initial,
        exclude_st=bool(raw_config.get("exclude_st", True)),
        exclude_suspended=bool(raw_config.get("exclude_suspended", True)),
        cost=cost,
    )
    result = run_topn_backtest(signal, daily_bar, backtest_config)
    portfolio_path = output_root / "portfolio_value.csv"
    positions_path = output_root / "positions.csv"
    trades_path = output_root / "trades.csv"
    result.portfolio_value.to_csv(portfolio_path, index=False)
    result.positions.to_csv(positions_path, index=False)
    result.trades.to_csv(trades_path, index=False)

    metrics = calculate_metrics(result.portfolio_value)
    metrics_path = output_root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    chart_paths = write_backtest_charts(result.portfolio_value, output_root / "charts") if write_charts else {}
    artifact_paths = {
        "signal": str(signal_path),
        "portfolio_value": str(portfolio_path),
        "positions": str(positions_path),
        "trades": str(trades_path),
        "metrics": str(metrics_path),
        **{name: str(path) for name, path in chart_paths.items()},
    }
    report_config = {
        "signal_name": resolved_signal,
        "market": backtest_config.market,
        "base_currency": backtest_config.base_currency,
        "benchmark": backtest_config.benchmark,
        "frequency": backtest_config.frequency,
        "top_n": backtest_config.top_n,
        "initial_capital": backtest_config.initial_capital,
        "buy_cost": cost.buy_cost,
        "sell_cost": cost.sell_cost,
        "min_cost": cost.min_cost,
    }
    report_path = write_backtest_report(metrics, report_config, artifact_paths, output_root / "report.md")
    summary_path = output_root / "run_summary.json"
    payload: dict[str, object] = {
        **artifact_paths,
        "report": str(report_path),
        "run_summary": str(summary_path),
        "metrics_summary": metrics,
    }
    if use_robustness:
        walk_forward = walk_forward_metrics(
            result.portfolio_value,
            window_days=min(252, max(20, len(result.portfolio_value) // 3)),
            step_days=min(63, max(10, len(result.portfolio_value) // 6)),
        )
        walk_forward_path = output_root / "walk_forward_metrics.csv"
        walk_forward.to_csv(walk_forward_path, index=False)
        cost_sensitivity = pd.DataFrame(_cost_sensitivity(signal, daily_bar, backtest_config))
        topn_sensitivity = pd.DataFrame(_topn_sensitivity(signal, daily_bar, backtest_config))
        robustness_paths = write_robustness_report(
            output_root,
            metrics,
            market_state_summary=market_state_decomposition(result.portfolio_value),
            cost_sensitivity=cost_sensitivity,
            topn_sensitivity=topn_sensitivity,
        )
        payload["walk_forward_metrics"] = str(walk_forward_path)
        payload["robustness"] = robustness_paths
    if use_qlib:
        qlib_result = run_qlib_backtest(signal, daily_bar, backtest_config, output_dir=output_root / "qlib")
        comparison_path = write_qlib_vs_pandas_comparison(
            qlib_result.metrics,
            metrics,
            output_path=output_root / "qlib_vs_pandas_comparison.md",
            same_strategy=not qlib_result.fallback_used,
        )
        payload["qlib"] = qlib_result.to_metadata()
        payload["qlib_vs_pandas_comparison"] = str(comparison_path)
    if use_vectorbt:
        vectorbt_result = run_vectorbt_grid(daily_bar, output_dir=output_root / "vectorbt_grid")
        payload["vectorbt"] = vectorbt_result.to_metadata()
    summary_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        summary = run_backtest(
            config_path=args.config,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            signal_name=args.signal,
            universe=args.universe,
            top_n=args.top_n,
            initial_capital=args.initial_capital,
            use_qlib=args.qlib,
            use_vectorbt=args.vectorbt,
            use_robustness=args.robustness,
            write_charts=not args.no_charts,
        )
        print(f"Portfolio value: {summary['portfolio_value']}")
        print(f"Positions: {summary['positions']}")
        print(f"Trades: {summary['trades']}")
        print(f"Metrics: {summary['metrics']}")
        if args.qlib:
            print(f"Qlib: {summary['qlib']}")
        if args.vectorbt:
            print(f"vectorbt: {summary['vectorbt']}")
        print(f"Report: {summary['report']}")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
