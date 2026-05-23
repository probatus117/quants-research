"""Pairwise factor correlation analysis."""

from __future__ import annotations

import pandas as pd


def factor_correlation_matrix(
    factor_values: pd.DataFrame,
    factor_column: str = "zscore",
) -> pd.DataFrame:
    """Return per-market pairwise factor correlations in long form."""
    required = {"date", "symbol", "factor_name", factor_column}
    missing = required.difference(factor_values.columns)
    if missing:
        raise ValueError(f"factor_values missing columns: {', '.join(sorted(missing))}")
    frame = factor_values.copy()
    if "market" not in frame.columns:
        frame["market"] = "cn"
    pivot = frame.pivot_table(
        index=["market", "date", "symbol"],
        columns="factor_name",
        values=factor_column,
        aggfunc="first",
    )
    rows: list[dict[str, object]] = []
    for market, group in pivot.groupby(level=0, sort=True):
        corr = group.droplevel(0).corr()
        for left in corr.index:
            for right in corr.columns:
                rows.append(
                    {
                        "market": market,
                        "factor_left": left,
                        "factor_right": right,
                        "correlation": float(corr.loc[left, right]),
                    }
                )
    return pd.DataFrame(rows)
