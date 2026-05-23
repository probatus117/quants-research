"""Quantile forward-return analysis for factor evaluation."""

from __future__ import annotations

import math

import pandas as pd

from src.quant.evaluation.input_builder import DEFAULT_PERIODS


class QuantileAnalysisError(ValueError):
    """Raised when quantile analysis inputs are invalid."""


def _assign_quantiles(series: pd.Series, quantiles: int) -> pd.Series:
    valid = series.dropna()
    output = pd.Series(pd.NA, index=series.index, dtype="Int64")
    if len(valid) < quantiles:
        return output
    ranks = valid.rank(method="first", ascending=True)
    labels = pd.qcut(ranks, q=quantiles, labels=range(1, quantiles + 1))
    output.loc[valid.index] = labels.astype("int64")
    return output


def calculate_quantile_returns(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...] | list[int] = DEFAULT_PERIODS,
    factor_column: str = "zscore",
    quantiles: int = 5,
) -> pd.DataFrame:
    """Calculate mean forward return by factor quantile, plus long-short spread."""
    if quantiles < 2:
        raise QuantileAnalysisError("quantiles must be at least 2")
    required = {"date", factor_column, *[f"forward_return_{period}d" for period in periods]}
    missing = required.difference(evaluation_input.columns)
    if missing:
        raise QuantileAnalysisError(f"evaluation input missing columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    group_keys = ["market", "date"] if "market" in evaluation_input.columns else ["date"]
    for key, date_group in evaluation_input.groupby(group_keys, sort=True):
        if len(group_keys) == 2:
            market, date = key
        else:
            market = "unknown"
            date = key
        assigned = date_group.copy()
        assigned["quantile"] = _assign_quantiles(assigned[factor_column], quantiles)
        for period in periods:
            return_column = f"forward_return_{period}d"
            grouped = assigned.dropna(subset=["quantile", return_column]).groupby("quantile", sort=True)
            quantile_means: dict[int, float] = {}
            for quantile, quantile_group in grouped:
                quantile_id = int(quantile)
                mean_return = float(quantile_group[return_column].mean())
                quantile_means[quantile_id] = mean_return
                rows.append(
                    {
                        "date": str(date),
                        "market": market,
                        "period": int(period),
                        "quantile": quantile_id,
                        "mean_forward_return": mean_return,
                        "count": int(len(quantile_group)),
                    }
                )
            if 1 in quantile_means and quantiles in quantile_means:
                spread = quantile_means[quantiles] - quantile_means[1]
                rows.append(
                    {
                        "date": str(date),
                        "market": market,
                        "period": int(period),
                        "quantile": "long_short",
                        "mean_forward_return": float(spread),
                        "count": int(grouped.size().sum()),
                    }
                )
    return pd.DataFrame(rows, columns=["date", "market", "period", "quantile", "mean_forward_return", "count"])


def summarize_quantile_returns(quantile_returns: pd.DataFrame) -> pd.DataFrame:
    """Average daily quantile returns by period and quantile."""
    required = {"period", "quantile", "mean_forward_return"}
    missing = required.difference(quantile_returns.columns)
    if missing:
        raise QuantileAnalysisError(f"quantile_returns missing columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, object]] = []
    group_keys = ["market", "period", "quantile"] if "market" in quantile_returns.columns else ["period", "quantile"]
    for key, group in quantile_returns.groupby(group_keys, sort=True):
        if len(group_keys) == 3:
            market, period, quantile = key
        else:
            market = "unknown"
            period, quantile = key
        values = pd.to_numeric(group["mean_forward_return"], errors="coerce").dropna()
        rows.append(
            {
                "market": market,
                "period": int(period),
                "quantile": str(quantile),
                "mean_forward_return": float(values.mean()) if not values.empty else math.nan,
                "observations": int(len(values)),
            }
        )
    return pd.DataFrame(rows)
