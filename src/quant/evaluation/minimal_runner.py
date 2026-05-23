"""Minimal single-factor evaluation runner."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.quant.evaluation.ic_analysis import calculate_ic_timeseries, summarize_ic
from src.quant.evaluation.input_builder import DEFAULT_PERIODS, EvaluationInputConfig, build_evaluation_input
from src.quant.evaluation.quantile_analysis import calculate_quantile_returns, summarize_quantile_returns


@dataclass(frozen=True)
class MinimalEvaluationConfig:
    """Configuration for the Phase 3 single-factor evaluation runner."""

    factor_name: str = "momentum_12_1"
    periods: tuple[int, ...] = DEFAULT_PERIODS
    universe: str | None = "sample_a"
    factor_column: str = "zscore"
    min_coverage: float = 0.80
    quantiles: int = 5


@dataclass(frozen=True)
class MinimalEvaluationResult:
    """Artifacts returned by the minimal evaluation runner."""

    config: MinimalEvaluationConfig
    evaluation_input: pd.DataFrame
    ic_timeseries: pd.DataFrame
    ic_summary: pd.DataFrame
    quantile_returns: pd.DataFrame
    quantile_summary: pd.DataFrame
    coverage: dict[str, object]
    factor_summary: dict[str, object]


def _coverage_report(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...],
    factor_column: str,
    min_coverage: float,
) -> dict[str, object]:
    by_date: list[dict[str, object]] = []
    warnings: list[str] = []
    period_columns = [f"forward_return_{period}d" for period in periods]
    group_keys = ["market", "date"] if "market" in evaluation_input.columns else ["date"]
    for key, group in evaluation_input.groupby(group_keys, sort=True):
        if len(group_keys) == 2:
            market, date = key
        else:
            market = "unknown"
            date = key
        universe_total = int(group["symbol"].nunique())
        factor_valid = int(group[factor_column].notna().sum())
        row: dict[str, object] = {
            "date": str(date),
            "market": market,
            "universe_total": universe_total,
            "factor_valid_count": factor_valid,
            "factor_coverage": factor_valid / universe_total if universe_total else 0.0,
        }
        for period, period_column in zip(periods, period_columns):
            both_valid = int(group[[factor_column, period_column]].dropna().shape[0])
            row[f"forward_return_{period}d_valid_count"] = both_valid
            row[f"forward_return_{period}d_coverage"] = both_valid / universe_total if universe_total else 0.0
        by_date.append(row)

    summary: dict[str, object] = {
        "min_coverage_threshold": float(min_coverage),
        "dates": int(len(by_date)),
    }
    coverage_frame = pd.DataFrame(by_date)
    if not coverage_frame.empty:
        columns = ["factor_coverage", *[f"forward_return_{period}d_coverage" for period in periods]]
        for column in columns:
            minimum = float(coverage_frame[column].min())
            mean = float(coverage_frame[column].mean())
            summary[f"{column}_min"] = minimum
            summary[f"{column}_mean"] = mean
            if minimum < min_coverage:
                warnings.append(f"{column} minimum {minimum:.3f} is below threshold {min_coverage:.3f}")
    return {"summary": summary, "by_date": by_date, "warnings": warnings}


def _factor_summary(
    config: MinimalEvaluationConfig,
    evaluation_input: pd.DataFrame,
    ic_summary: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    coverage: dict[str, object],
) -> dict[str, object]:
    return {
        "factor_name": config.factor_name,
        "universe": config.universe,
        "factor_column": config.factor_column,
        "periods": list(config.periods),
        "markets": sorted(evaluation_input["market"].dropna().unique().tolist()) if "market" in evaluation_input.columns else [],
        "start_date": str(evaluation_input["date"].min()),
        "end_date": str(evaluation_input["date"].max()),
        "row_count": int(len(evaluation_input)),
        "ic_summary": ic_summary.to_dict(orient="records"),
        "quantile_summary": quantile_summary.to_dict(orient="records"),
        "coverage_summary": coverage["summary"],
        "coverage_warnings": coverage["warnings"],
    }


def run_minimal_evaluation(
    factor_values: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: MinimalEvaluationConfig | None = None,
) -> MinimalEvaluationResult:
    """Run Phase 3's minimal factor evaluation using in-memory tables."""
    cfg = config or MinimalEvaluationConfig()
    evaluation_input = build_evaluation_input(
        factor_values,
        daily_bar,
        EvaluationInputConfig(factor_name=cfg.factor_name, periods=cfg.periods, universe=cfg.universe),
    )
    ic_timeseries = calculate_ic_timeseries(evaluation_input, cfg.periods, cfg.factor_column)
    ic_summary = summarize_ic(ic_timeseries)
    quantile_returns = calculate_quantile_returns(evaluation_input, cfg.periods, cfg.factor_column, cfg.quantiles)
    quantile_summary = summarize_quantile_returns(quantile_returns)
    coverage = _coverage_report(evaluation_input, cfg.periods, cfg.factor_column, cfg.min_coverage)
    factor_summary = _factor_summary(cfg, evaluation_input, ic_summary, quantile_summary, coverage)
    return MinimalEvaluationResult(
        config=cfg,
        evaluation_input=evaluation_input,
        ic_timeseries=ic_timeseries,
        ic_summary=ic_summary,
        quantile_returns=quantile_returns,
        quantile_summary=quantile_summary,
        coverage=coverage,
        factor_summary=factor_summary,
    )
