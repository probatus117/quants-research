"""Phase 7b robustness report helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.backtest.metrics import calculate_metrics
from src.quant.evaluation.ic_analysis import calculate_ic_timeseries, summarize_ic


DEFAULT_ROBUSTNESS_THRESHOLDS = {
    "min_sharpe": 0.5,
    "max_drawdown_floor": -0.35,
    "min_rank_ic_mean": 0.0,
    "max_factor_correlation": 0.7,
}


def classify_robustness(metrics: dict[str, Any], thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    """Classify a result as robust or not based on explicit thresholds."""

    cfg = {**DEFAULT_ROBUSTNESS_THRESHOLDS, **(thresholds or {})}
    checks = {}
    if "sharpe" in metrics:
        checks["sharpe"] = float(metrics["sharpe"]) >= cfg["min_sharpe"]
    if "max_drawdown" in metrics:
        checks["max_drawdown"] = float(metrics["max_drawdown"]) >= cfg["max_drawdown_floor"]
    if "rank_ic_mean" in metrics:
        checks["rank_ic_mean"] = float(metrics["rank_ic_mean"]) >= cfg["min_rank_ic_mean"]
    label = "robust" if checks and all(checks.values()) else "not_robust"
    return {"label": label, "thresholds": cfg, "checks": checks}


def yearly_factor_summary(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...] = (5, 20, 60),
    factor_column: str = "zscore",
) -> pd.DataFrame:
    """Return IC summary by market and calendar year."""

    frame = evaluation_input.copy()
    if "market" not in frame.columns:
        frame["market"] = "unknown"
    frame["date"] = pd.to_datetime(frame["date"])
    rows = []
    for (market, year), group in frame.groupby(["market", frame["date"].dt.year], sort=True):
        if len(group) < 2:
            continue
        summary = summarize_ic(calculate_ic_timeseries(group, periods, factor_column))
        long_short = _long_short_returns(group, periods, factor_column)
        for item in summary.to_dict(orient="records"):
            rows.append({"market": market, "year": int(year), **item, "long_short_return": long_short.get(int(item["period"]))})
    return pd.DataFrame(rows)


def market_cap_group_summary(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...] = (5, 20, 60),
    factor_column: str = "zscore",
    bucket_column: str = "market_cap_bucket",
) -> pd.DataFrame:
    """Return IC summary by market-cap bucket when the bucket column exists."""

    if bucket_column not in evaluation_input.columns:
        return pd.DataFrame(columns=["market", bucket_column, "period", "ic_mean", "rank_ic_mean"])
    rows = []
    for (market, bucket), group in evaluation_input.groupby(["market", bucket_column], sort=True):
        if len(group) < 2:
            continue
        summary = summarize_ic(calculate_ic_timeseries(group, periods, factor_column))
        long_short = _long_short_returns(group, periods, factor_column)
        for item in summary.to_dict(orient="records"):
            rows.append({"market": market, bucket_column: bucket, **item, "long_short_return": long_short.get(int(item["period"]))})
    return pd.DataFrame(rows)


def _long_short_returns(
    frame: pd.DataFrame,
    periods: tuple[int, ...],
    factor_column: str,
) -> dict[int, float | None]:
    result: dict[int, float | None] = {}
    for period in periods:
        column = f"forward_return_{period}d"
        if column not in frame.columns:
            result[int(period)] = None
            continue
        spreads = []
        for _, group in frame.dropna(subset=[factor_column, column]).groupby("date", sort=True):
            if len(group) < 5:
                continue
            ranked = group.assign(_rank=group[factor_column].rank(pct=True))
            high = ranked[ranked["_rank"] >= 0.8][column].mean()
            low = ranked[ranked["_rank"] <= 0.2][column].mean()
            spreads.append(float(high - low))
        result[int(period)] = float(pd.Series(spreads).mean()) if spreads else None
    return result


def market_state_decomposition(portfolio_value: pd.DataFrame) -> pd.DataFrame:
    """Summarize backtest metrics in bull/bear/sideways benchmark regimes."""

    frame = portfolio_value.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if "benchmark_return" not in frame.columns:
        frame["benchmark_return"] = 0.0
    rolling = (1.0 + frame["benchmark_return"].astype(float)).rolling(20, min_periods=2).apply(lambda values: values.prod() - 1.0)
    frame["market_state"] = "sideways"
    frame.loc[rolling > 0.05, "market_state"] = "bull"
    frame.loc[rolling < -0.05, "market_state"] = "bear"
    rows = []
    for state, group in frame.groupby("market_state", sort=True):
        if len(group) < 2:
            continue
        metrics = calculate_metrics(group)
        rows.append(
            {
                "market_state": state,
                "observations": int(len(group)),
                "market": metrics.get("market", "unknown"),
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "total_return": metrics["total_return"],
                "excess_return": metrics["excess_return"],
            }
        )
    return pd.DataFrame(rows)


def write_robustness_report(
    output_dir: str | Path,
    metrics: dict[str, Any],
    yearly_summary: pd.DataFrame | None = None,
    cap_group_summary: pd.DataFrame | None = None,
    market_state_summary: pd.DataFrame | None = None,
    cost_sensitivity: pd.DataFrame | None = None,
    topn_sensitivity: pd.DataFrame | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, str]:
    """Write JSON/Markdown/CSV artifacts for Phase 7b robustness checks."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    classification = classify_robustness(metrics, thresholds)
    json_path = output / "robustness_report.json"
    md_path = output / "robustness_report.md"
    json_path.write_text(json.dumps(classification, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifacts = {"robustness_report": str(json_path), "robustness_markdown": str(md_path)}
    optional_frames = {
        "yearly_factor_summary": yearly_summary,
        "market_cap_group_summary": cap_group_summary,
        "market_state_decomposition": market_state_summary,
        "cost_sensitivity": cost_sensitivity,
        "topn_sensitivity": topn_sensitivity,
    }
    for name, frame in optional_frames.items():
        if frame is not None:
            path = output / f"{name}.csv"
            frame.to_csv(path, index=False)
            artifacts[name] = str(path)

    lines = [
        "# Robustness Report",
        "",
        f"- label: `{classification['label']}`",
        f"- checks: `{json.dumps(classification['checks'], sort_keys=True)}`",
        "",
        "## Artifacts",
        *[f"- `{name}`: `{path}`" for name, path in sorted(artifacts.items()) if name != "robustness_markdown"],
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return artifacts
