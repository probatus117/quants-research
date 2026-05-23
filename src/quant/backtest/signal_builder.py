"""Build backtest signals from factor values."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.quant.data.storage import write_parquet

COMPOSITE_V1_WEIGHTS = {
    "value_bp": 0.34,
    "momentum_12_1": 0.33,
    "lowvol_60d": 0.33,
}

SIGNAL_COLUMNS = (
    "date",
    "market",
    "symbol",
    "signal_name",
    "raw_score",
    "score",
    "universe",
    "source_factors",
)


@dataclass(frozen=True)
class SignalConfig:
    """Configuration for factor-to-signal conversion."""

    signal_name: str = "composite_v1"
    factor_weights: dict[str, float] = field(default_factory=lambda: dict(COMPOSITE_V1_WEIGHTS))
    factor_column: str = "zscore"
    universe: str | None = "sample_a"
    min_factors: int | None = None


def _normalize_by_date(df: pd.DataFrame, raw_column: str = "raw_score") -> pd.Series:
    def normalize(group: pd.Series) -> pd.Series:
        std = group.std(ddof=1)
        if pd.isna(std) or std == 0:
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / std

    group_keys = ["market", "date"] if "market" in df.columns else ["date"]
    return df.groupby(group_keys, sort=False)[raw_column].transform(normalize)


def build_single_factor_signal(
    factor_values: pd.DataFrame,
    factor_name: str,
    factor_column: str = "zscore",
    universe: str | None = "sample_a",
) -> pd.DataFrame:
    """Create a normalized signal from one factor column."""
    required = {"date", "symbol", "factor_name", factor_column, "universe"}
    missing = sorted(required - set(factor_values.columns))
    if missing:
        raise ValueError(f"factor_values missing columns: {', '.join(missing)}")

    df = factor_values[factor_values["factor_name"] == factor_name].copy()
    if universe is not None:
        df = df[df["universe"] == universe]
    if df.empty:
        raise ValueError(f"No factor rows found for factor={factor_name!r}, universe={universe!r}")

    if "market" not in df.columns:
        df["market"] = "cn"
    signal = df[["date", "market", "symbol", "universe", factor_column]].rename(columns={factor_column: "raw_score"})
    signal["signal_name"] = factor_name
    signal["source_factors"] = factor_name
    signal = signal.dropna(subset=["raw_score"]).copy()
    signal["score"] = _normalize_by_date(signal)
    return (
        signal[list(SIGNAL_COLUMNS)]
        .sort_values(["market", "date", "score", "symbol"], ascending=[True, True, False, True])
        .reset_index(drop=True)
    )


def build_composite_signal(factor_values: pd.DataFrame, config: SignalConfig | None = None) -> pd.DataFrame:
    """Create a weighted composite score, then normalize it by date."""
    cfg = config or SignalConfig()
    required = {"date", "symbol", "factor_name", cfg.factor_column, "universe"}
    missing = sorted(required - set(factor_values.columns))
    if missing:
        raise ValueError(f"factor_values missing columns: {', '.join(missing)}")
    if not cfg.factor_weights:
        raise ValueError("factor_weights must not be empty")

    df = factor_values[factor_values["factor_name"].isin(cfg.factor_weights)].copy()
    if "market" not in df.columns:
        df["market"] = "cn"
    if cfg.universe is not None:
        df = df[df["universe"] == cfg.universe]
    if df.empty:
        raise ValueError("No factor rows found for composite signal")

    pivot = df.pivot_table(
        index=["date", "market", "symbol", "universe"],
        columns="factor_name",
        values=cfg.factor_column,
        aggfunc="first",
    )
    min_factors = cfg.min_factors if cfg.min_factors is not None else len(cfg.factor_weights)
    available = pivot[list(cfg.factor_weights)].notna().sum(axis=1)
    weighted = sum(pivot[factor] * weight for factor, weight in cfg.factor_weights.items())
    signal = pivot.reset_index()[["date", "market", "symbol", "universe"]]
    signal["raw_score"] = weighted.to_numpy()
    signal.loc[available.to_numpy() < min_factors, "raw_score"] = pd.NA
    signal = signal.dropna(subset=["raw_score"]).copy()
    signal["signal_name"] = cfg.signal_name
    signal["source_factors"] = ",".join(cfg.factor_weights)
    signal["score"] = _normalize_by_date(signal)
    return (
        signal[list(SIGNAL_COLUMNS)]
        .sort_values(["market", "date", "score", "symbol"], ascending=[True, True, False, True])
        .reset_index(drop=True)
    )


def write_signal(signal: pd.DataFrame, parquet_root: str | Path) -> Path:
    """Write signal.parquet using the standard quant storage layout."""
    missing = sorted(set(SIGNAL_COLUMNS) - set(signal.columns))
    if missing:
        raise ValueError(f"signal missing columns: {', '.join(missing)}")
    return write_parquet(signal[list(SIGNAL_COLUMNS)], "signal", root=parquet_root)
