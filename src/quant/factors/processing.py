"""Cross-sectional factor post-processing helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_mad(series: pd.Series, n: float = 3.0) -> pd.Series:
    """Clip extreme values using median absolute deviation."""
    numeric = pd.to_numeric(series, errors="coerce")
    median = numeric.median(skipna=True)
    mad = (numeric - median).abs().median(skipna=True)
    if pd.isna(median) or pd.isna(mad) or mad == 0:
        return numeric.copy()
    lower = median - n * 1.4826 * mad
    upper = median + n * 1.4826 * mad
    return numeric.clip(lower=lower, upper=upper)


def zscore(series: pd.Series) -> pd.Series:
    """Standardize a series using sample standard deviation."""
    numeric = pd.to_numeric(series, errors="coerce")
    mean = numeric.mean(skipna=True)
    std = numeric.std(skipna=True)
    if pd.isna(mean) or pd.isna(std) or std == 0:
        return pd.Series(np.nan, index=series.index, dtype="float64")
    return (numeric - mean) / std


def rank_percentile(series: pd.Series, direction: int = 1) -> pd.Series:
    """Return percentile ranks in score direction, where 1.0 is best."""
    numeric = pd.to_numeric(series, errors="coerce")
    ascending = direction >= 0
    return numeric.rank(method="average", pct=True, ascending=ascending)


def neutralize(
    df: pd.DataFrame,
    value_column: str = "zscore",
    by: list[str] | None = None,
) -> pd.Series:
    """Neutralize a factor column by industry dummies and log market cap."""
    controls = by or ["industry", "log_market_cap"]
    if value_column not in df.columns:
        raise ValueError(f"neutralize: missing value column {value_column!r}")
    if not set(controls).issubset(df.columns):
        return df[value_column].copy()

    output = pd.Series(np.nan, index=df.index, dtype="float64")
    group_keys = ["factor_name", "market", "date"] if "market" in df.columns else ["factor_name", "date"]
    for _, group in df.groupby(group_keys, sort=False):
        y = pd.to_numeric(group[value_column], errors="coerce")
        valid = y.notna()
        if "log_market_cap" in controls:
            valid &= pd.to_numeric(group["log_market_cap"], errors="coerce").notna()
        if valid.sum() < 3:
            output.loc[group.index] = y
            continue

        design_parts = []
        if "industry" in controls:
            dummies = pd.get_dummies(group.loc[valid, "industry"].astype("string"), drop_first=True, dtype=float)
            if not dummies.empty:
                design_parts.append(dummies)
        if "log_market_cap" in controls:
            design_parts.append(pd.DataFrame({"log_market_cap": pd.to_numeric(group.loc[valid, "log_market_cap"])}, index=group.loc[valid].index))
        if not design_parts:
            output.loc[group.index] = y
            continue

        x = pd.concat(design_parts, axis=1)
        x.insert(0, "intercept", 1.0)
        try:
            beta, *_ = np.linalg.lstsq(x.to_numpy(dtype=float), y.loc[valid].to_numpy(dtype=float), rcond=None)
        except np.linalg.LinAlgError:
            output.loc[group.index] = y
            continue
        fitted = x.to_numpy(dtype=float) @ beta
        output.loc[group.loc[valid].index] = y.loc[valid].to_numpy(dtype=float) - fitted
        output.loc[group.loc[~valid].index] = y.loc[~valid]
    return output


def process_factor_values(df: pd.DataFrame) -> pd.DataFrame:
    """Add winsorized, zscore, and percentile columns by factor/date cross-section."""
    required = {"date", "symbol", "factor_name", "raw_value", "direction", "universe"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"factor values missing columns: {', '.join(sorted(missing))}")

    processed = df.copy()
    processed["raw_value"] = pd.to_numeric(processed["raw_value"], errors="coerce")
    if "market" not in processed.columns:
        processed["market"] = "cn"
    group_keys = ["factor_name", "market", "date"]
    processed["winsorized_value"] = processed.groupby(group_keys)["raw_value"].transform(winsorize_mad)
    processed["zscore"] = processed.groupby(group_keys)["winsorized_value"].transform(zscore)
    processed["percentile"] = np.nan
    for _, group in processed.groupby(group_keys):
        processed.loc[group.index, "percentile"] = rank_percentile(
            group["winsorized_value"],
            int(group["direction"].iloc[0]),
        )
    processed["zscore_neutral"] = neutralize(processed)
    return processed[
        [
            "date",
            "market",
            "symbol",
            "factor_name",
            "raw_value",
            "winsorized_value",
            "zscore",
            "percentile",
            "direction",
            "universe",
            "zscore_neutral",
        ]
    ].sort_values(["factor_name", "market", "date", "symbol"]).reset_index(drop=True)
