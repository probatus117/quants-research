"""Information coefficient analysis for single-factor evaluation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.quant.evaluation.input_builder import DEFAULT_PERIODS


class ICAnalysisError(ValueError):
    """Raised when IC analysis inputs are invalid."""


def _period_column(period: int) -> str:
    return f"forward_return_{int(period)}d"


def _safe_ratio(mean: float, std: float) -> float:
    if pd.isna(mean) or pd.isna(std) or std == 0:
        return math.nan
    return mean / std


def calculate_ic_timeseries(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...] | list[int] = DEFAULT_PERIODS,
    factor_column: str = "zscore",
) -> pd.DataFrame:
    """Calculate daily Pearson IC and Spearman rank IC for each forward-return period."""
    required = {"date", factor_column, *[_period_column(period) for period in periods]}
    missing = required.difference(evaluation_input.columns)
    if missing:
        raise ICAnalysisError(f"evaluation input missing columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for date, date_group in evaluation_input.groupby("date", sort=True):
        for period in periods:
            period_column = _period_column(period)
            valid = date_group[[factor_column, period_column]].dropna()
            if len(valid) < 2:
                ic = math.nan
                rank_ic = math.nan
            else:
                ic = valid[factor_column].corr(valid[period_column], method="pearson")
                factor_rank = valid[factor_column].rank(method="average")
                return_rank = valid[period_column].rank(method="average")
                rank_ic = factor_rank.corr(return_rank, method="pearson")
            rows.append(
                {
                    "date": str(date),
                    "period": int(period),
                    "ic": float(ic) if pd.notna(ic) else math.nan,
                    "rank_ic": float(rank_ic) if pd.notna(rank_ic) else math.nan,
                    "count": int(len(valid)),
                }
            )
    return pd.DataFrame(rows, columns=["date", "period", "ic", "rank_ic", "count"])


def summarize_ic(ic_timeseries: pd.DataFrame) -> pd.DataFrame:
    """Summarize IC statistics by period."""
    required = {"period", "ic", "rank_ic"}
    missing = required.difference(ic_timeseries.columns)
    if missing:
        raise ICAnalysisError(f"ic_timeseries missing columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for period, group in ic_timeseries.groupby("period", sort=True):
        ic = pd.to_numeric(group["ic"], errors="coerce").dropna()
        rank_ic = pd.to_numeric(group["rank_ic"], errors="coerce").dropna()
        ic_mean = ic.mean() if not ic.empty else math.nan
        ic_std = ic.std(ddof=1) if len(ic) > 1 else math.nan
        rank_mean = rank_ic.mean() if not rank_ic.empty else math.nan
        rank_std = rank_ic.std(ddof=1) if len(rank_ic) > 1 else math.nan
        rows.append(
            {
                "period": int(period),
                "ic_mean": float(ic_mean) if pd.notna(ic_mean) else math.nan,
                "ic_std": float(ic_std) if pd.notna(ic_std) else math.nan,
                "icir": float(_safe_ratio(ic_mean, ic_std)),
                "rank_ic_mean": float(rank_mean) if pd.notna(rank_mean) else math.nan,
                "rank_ic_std": float(rank_std) if pd.notna(rank_std) else math.nan,
                "rank_icir": float(_safe_ratio(rank_mean, rank_std)),
                "ic_positive_ratio": float((ic > 0).mean()) if not ic.empty else math.nan,
                "observations": int(len(ic)),
            }
        )
    return pd.DataFrame(rows)


def ic_summary_to_records(summary: pd.DataFrame) -> list[dict[str, object]]:
    """Convert IC summary to JSON-friendly records with stable numeric nulls."""
    records = summary.replace({np.nan: None}).to_dict(orient="records")
    for record in records:
        record["period"] = int(record["period"])
        record["observations"] = int(record["observations"])
    return records
