"""Build factor evaluation inputs from factor values and adjusted prices."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


DEFAULT_PERIODS = (5, 20, 60)
FACTOR_SCORE_COLUMNS = ("zscore", "percentile", "winsorized_value", "raw_value")


class EvaluationInputError(ValueError):
    """Raised when factor evaluation input data is invalid."""


@dataclass(frozen=True)
class EvaluationInputConfig:
    """Input construction parameters for single-factor evaluation."""

    factor_name: str
    periods: tuple[int, ...] = DEFAULT_PERIODS
    universe: str | None = None


def _validate_periods(periods: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    normalized = tuple(int(period) for period in periods)
    if not normalized or any(period <= 0 for period in normalized):
        raise EvaluationInputError("forward return periods must be positive integers")
    return normalized


def _require_columns(df: pd.DataFrame, columns: set[str], table_name: str) -> None:
    missing = columns.difference(df.columns)
    if missing:
        raise EvaluationInputError(f"{table_name} missing columns: {', '.join(sorted(missing))}")


def add_forward_returns(daily_bar: pd.DataFrame, periods: tuple[int, ...] | list[int] = DEFAULT_PERIODS) -> pd.DataFrame:
    """Return date-symbol adjusted prices with forward returns for each period."""
    normalized_periods = _validate_periods(periods)
    _require_columns(daily_bar, {"date", "symbol", "adj_close"}, "daily_bar")
    identity_columns = ["date", "symbol"]
    if "market" in daily_bar.columns:
        identity_columns.insert(1, "market")
    prices = daily_bar[identity_columns + ["adj_close"]].copy()
    prices["adj_close"] = pd.to_numeric(prices["adj_close"], errors="coerce")
    sort_keys = ["market", "symbol", "date"] if "market" in prices.columns else ["symbol", "date"]
    group_keys = ["market", "symbol"] if "market" in prices.columns else ["symbol"]
    prices = prices.sort_values(sort_keys).reset_index(drop=True)

    grouped = prices.groupby(group_keys, sort=False)["adj_close"]
    for period in normalized_periods:
        future_price = grouped.shift(-period)
        returns = (future_price / prices["adj_close"]) - 1.0
        prices[f"forward_return_{period}d"] = returns.where((future_price > 0) & (prices["adj_close"] > 0))
    return prices


def build_evaluation_input(
    factor_values: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: EvaluationInputConfig | str,
    periods: tuple[int, ...] | list[int] | None = None,
    universe: str | None = None,
) -> pd.DataFrame:
    """Merge one factor's values with forward returns at date-symbol granularity."""
    if isinstance(config, str):
        config = EvaluationInputConfig(
            factor_name=config,
            periods=_validate_periods(periods or DEFAULT_PERIODS),
            universe=universe,
        )
    normalized_periods = _validate_periods(periods or config.periods)
    _require_columns(
        factor_values,
        {"date", "symbol", "factor_name", "raw_value", "direction", "universe", *FACTOR_SCORE_COLUMNS},
        "factor_values",
    )

    factor = factor_values[factor_values["factor_name"] == config.factor_name].copy()
    if config.universe is not None:
        factor = factor[factor["universe"] == config.universe].copy()
    if factor.empty:
        raise EvaluationInputError(f"No factor values found for {config.factor_name!r}")
    if "zscore_neutral" not in factor.columns:
        factor["zscore_neutral"] = factor["zscore"]

    if "market" not in factor.columns:
        factor["market"] = "cn"
    forward_returns = add_forward_returns(daily_bar, normalized_periods)
    merge_keys = ["date", "market", "symbol"] if "market" in forward_returns.columns else ["date", "symbol"]
    merged = factor.merge(forward_returns, on=merge_keys, how="left", validate="many_to_one")
    columns = [
        "date",
        "market",
        "symbol",
        "factor_name",
        "raw_value",
        "winsorized_value",
        "zscore",
        "zscore_neutral",
        "percentile",
        "direction",
        "universe",
        "adj_close",
        *[f"forward_return_{period}d" for period in normalized_periods],
    ]
    return merged[columns].sort_values(["market", "date", "symbol"]).reset_index(drop=True)
