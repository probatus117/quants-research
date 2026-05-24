"""Optional Alphalens adapter for factor evaluation tear sheets."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation
from src.quant.reports.factor_report import write_factor_report

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "stock_skills_matplotlib"))

try:  # pragma: no cover - environment-specific.
    import alphalens as al

    HAS_ALPHALENS = True
    ALPHALENS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    al = None
    HAS_ALPHALENS = False
    ALPHALENS_IMPORT_ERROR = exc


ALPHALENS_SKIP_REASON = "alphalens-reloaded is not installed; using minimal pandas evaluation report"


@dataclass(frozen=True)
class AlphalensCapability:
    """Runtime availability for the optional Alphalens integration."""

    available: bool
    skip_reason: str | None = None


@dataclass(frozen=True)
class AlphalensRunResult:
    """Audit payload for Alphalens or fallback execution."""

    available: bool
    fallback_used: bool
    skip_reason: str | None
    artifacts: dict[str, str]
    ic_comparison: dict[str, float | None]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "alphalens",
            "available": self.available,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "artifacts": self.artifacts,
            "ic_comparison": self.ic_comparison,
        }


def check_alphalens_capability() -> AlphalensCapability:
    """Return Alphalens availability without making it a hard dependency."""

    if HAS_ALPHALENS and al is not None:
        return AlphalensCapability(available=True)
    if ALPHALENS_IMPORT_ERROR is not None:
        return AlphalensCapability(
            available=False,
            skip_reason=f"alphalens-reloaded import failed: {ALPHALENS_IMPORT_ERROR}; using minimal pandas evaluation report",
        )
    return AlphalensCapability(available=False, skip_reason=ALPHALENS_SKIP_REASON)


def _factor_series(evaluation_input: pd.DataFrame, factor_column: str) -> pd.Series:
    frame = evaluation_input.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.dropna(subset=[factor_column])
    asset = frame["market"].astype(str) + ":" + frame["symbol"].astype(str)
    return pd.Series(
        frame[factor_column].astype(float).to_numpy(),
        index=pd.MultiIndex.from_arrays([frame["date"], asset], names=["date", "asset"]),
        name=factor_column,
    ).sort_index()


def _prices(daily_bar: pd.DataFrame) -> pd.DataFrame:
    bars = daily_bar.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    if "market" not in bars.columns:
        bars["market"] = "unknown"
    bars["asset"] = bars["market"].astype(str) + ":" + bars["symbol"].astype(str)
    return bars.pivot_table(index="date", columns="asset", values="adj_close", aggfunc="first").sort_index()


def _write_skip_artifacts(
    factor_values: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: MinimalEvaluationConfig,
    output_dir: Path,
    skip_reason: str,
) -> AlphalensRunResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    minimal = run_minimal_evaluation(factor_values, daily_bar, config)
    report_path = write_factor_report(minimal.factor_summary, minimal.coverage, output_dir / "minimal_report.md")
    summary_path = output_dir / "alphalens_summary.json"
    artifacts = {"minimal_report": str(report_path), "summary": str(summary_path)}
    result = AlphalensRunResult(
        available=False,
        fallback_used=True,
        skip_reason=skip_reason,
        artifacts=artifacts,
        ic_comparison={"max_abs_ic_mean_diff": None, "max_abs_rank_ic_mean_diff": None},
    )
    summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _ic_comparison(minimal_ic: pd.DataFrame, alphalens_factor_data: pd.DataFrame) -> dict[str, float | None]:
    if alphalens_factor_data.empty:
        return {"max_abs_ic_mean_diff": None, "max_abs_rank_ic_mean_diff": None}
    forward_columns = [column for column in alphalens_factor_data.columns if str(column).endswith("D")]
    if not forward_columns:
        return {"max_abs_ic_mean_diff": None, "max_abs_rank_ic_mean_diff": None}
    rows: list[dict[str, float]] = []
    frame = alphalens_factor_data.reset_index()
    for column in forward_columns:
        period = int(str(column).rstrip("D"))
        by_date = []
        for _, group in frame.groupby("date", sort=True):
            if group["factor"].nunique(dropna=True) < 2 or group[column].nunique(dropna=True) < 2:
                continue
            rank_factor = group["factor"].rank()
            rank_forward = group[column].rank()
            by_date.append(
                {
                    "ic": float(group["factor"].corr(group[column], method="pearson")),
                    "rank_ic": float(rank_factor.corr(rank_forward, method="pearson")),
                }
            )
        if by_date:
            rows.append(
                {
                    "period": period,
                    "ic_mean": float(pd.DataFrame(by_date)["ic"].mean()),
                    "rank_ic_mean": float(pd.DataFrame(by_date)["rank_ic"].mean()),
                }
            )
    if not rows:
        return {"max_abs_ic_mean_diff": None, "max_abs_rank_ic_mean_diff": None}
    al_summary = pd.DataFrame(rows)
    merged = minimal_ic.merge(al_summary, on="period", suffixes=("_minimal", "_alphalens"))
    if merged.empty:
        return {"max_abs_ic_mean_diff": None, "max_abs_rank_ic_mean_diff": None}
    return {
        "max_abs_ic_mean_diff": float((merged["ic_mean_minimal"] - merged["ic_mean_alphalens"]).abs().max()),
        "max_abs_rank_ic_mean_diff": float((merged["rank_ic_mean_minimal"] - merged["rank_ic_mean_alphalens"]).abs().max()),
    }


def _tear_sheet_frames(factor_data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frame = factor_data.reset_index()
    forward_columns = [column for column in frame.columns if str(column).endswith("D")]
    first_forward = forward_columns[0] if forward_columns else None
    ic_rows = []
    quantile_rows = []
    turnover_rows = []
    autocorr_rows = []
    if first_forward is not None:
        for date, group in frame.groupby("date", sort=True):
            if group["factor"].nunique(dropna=True) >= 2 and group[first_forward].nunique(dropna=True) >= 2:
                ic_rows.append(
                    {
                        "date": date,
                        "ic": float(group["factor"].corr(group[first_forward])),
                        "rank_ic": float(group["factor"].rank().corr(group[first_forward].rank())),
                    }
                )
        quantile_rows = (
            frame.groupby("factor_quantile", sort=True)[first_forward]
            .mean()
            .reset_index()
            .rename(columns={first_forward: "mean_forward_return"})
            .to_dict(orient="records")
        )
    if {"asset", "factor_quantile"}.issubset(frame.columns):
        ordered = frame.sort_values(["asset", "date"]).copy()
        ordered["previous_quantile"] = ordered.groupby("asset")["factor_quantile"].shift(1)
        changed = ordered[ordered["previous_quantile"].notna()].copy()
        if not changed.empty:
            turnover_rows = (
                changed.assign(changed=changed["factor_quantile"] != changed["previous_quantile"])
                .groupby("date", sort=True)["changed"]
                .mean()
                .reset_index(name="turnover")
                .to_dict(orient="records")
            )
        autocorr = ordered.groupby("asset")["factor"].apply(lambda series: series.astype(float).autocorr()).dropna()
        autocorr_rows = [{"metric": "factor_autocorrelation_mean", "value": float(autocorr.mean())}] if not autocorr.empty else []
    return {
        "ic": pd.DataFrame(ic_rows),
        "quantile_returns": pd.DataFrame(quantile_rows),
        "turnover": pd.DataFrame(turnover_rows),
        "factor_autocorrelation": pd.DataFrame(autocorr_rows),
    }


def _write_compact_tear_sheet(factor_data: pd.DataFrame, output: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    frames = _tear_sheet_frames(factor_data)
    artifacts: dict[str, str] = {}
    for name, frame in frames.items():
        csv_path = output / f"{name}.csv"
        frame.to_csv(csv_path, index=False)
        artifacts[name] = str(csv_path)

    chart_specs = [
        ("ic", "date", "rank_ic", "Rank IC"),
        ("quantile_returns", "factor_quantile", "mean_forward_return", "Quantile Returns"),
        ("turnover", "date", "turnover", "Quantile Turnover"),
        ("factor_autocorrelation", "metric", "value", "Factor Autocorrelation"),
    ]
    png_paths = []
    for name, x_col, y_col, title in chart_specs:
        frame = frames[name]
        path = output / f"{name}.png"
        plt.figure(figsize=(7, 4))
        if not frame.empty and {x_col, y_col}.issubset(frame.columns):
            if name in {"quantile_returns", "factor_autocorrelation"}:
                plt.bar(frame[x_col].astype(str), frame[y_col].astype(float))
            else:
                plt.plot(pd.to_datetime(frame[x_col]) if x_col == "date" else frame[x_col], frame[y_col].astype(float))
        plt.title(title)
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
        artifacts[f"{name}_png"] = str(path)
        png_paths.append(path)

    html_path = output / "tear_sheet.html"
    html_path.write_text(
        "\n".join(
            [
                "<html><body><h1>Alphalens Compact Tear Sheet</h1>",
                "<ul>",
                "<li>IC summary</li>",
                "<li>Quantile returns</li>",
                "<li>Turnover</li>",
                "<li>Factor autocorrelation</li>",
                "</ul>",
                *[f'<img src="{path.name}" alt="{path.stem}">' for path in png_paths],
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )
    artifacts["tear_sheet_html"] = str(html_path)
    return artifacts


def run_alphalens_evaluation(
    factor_values: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: MinimalEvaluationConfig | None = None,
    output_dir: str | Path = "data/quant/evaluation/alphalens",
    enabled: bool = True,
) -> AlphalensRunResult:
    """Run Alphalens tear sheet when available, otherwise write audited fallback artifacts."""

    cfg = config or MinimalEvaluationConfig()
    output = Path(output_dir)
    capability = check_alphalens_capability()
    if not enabled:
        return _write_skip_artifacts(
            factor_values,
            daily_bar,
            cfg,
            output,
            "alphalens disabled by caller; using minimal pandas evaluation report",
        )
    if not capability.available or al is None:
        return _write_skip_artifacts(factor_values, daily_bar, cfg, output, capability.skip_reason or ALPHALENS_SKIP_REASON)

    output.mkdir(parents=True, exist_ok=True)
    minimal = run_minimal_evaluation(factor_values, daily_bar, cfg)
    factor = _factor_series(minimal.evaluation_input, cfg.factor_column)
    prices = _prices(daily_bar)
    factor_data = al.utils.get_clean_factor_and_forward_returns(
        factor=factor,
        prices=prices,
        periods=cfg.periods,
        quantiles=cfg.quantiles,
        max_loss=1.0,
    )

    tear_sheet_artifacts = _write_compact_tear_sheet(factor_data, output)
    factor_data_path = output / "alphalens_factor_data.csv"
    factor_data.to_csv(factor_data_path)
    comparison = _ic_comparison(minimal.ic_summary, factor_data)
    summary_path = output / "alphalens_summary.json"
    artifacts = {
        "factor_data": str(factor_data_path),
        "summary": str(summary_path),
        **tear_sheet_artifacts,
    }
    result = AlphalensRunResult(
        available=True,
        fallback_used=False,
        skip_reason=None,
        artifacts=artifacts,
        ic_comparison=comparison,
    )
    summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
