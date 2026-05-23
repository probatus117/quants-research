"""IC decay calculation across forward-return horizons."""

from __future__ import annotations

import pandas as pd

from src.quant.evaluation.ic_analysis import calculate_ic_timeseries, summarize_ic
from src.quant.evaluation.input_builder import DEFAULT_PERIODS


def calculate_ic_decay(
    evaluation_input: pd.DataFrame,
    periods: tuple[int, ...] | list[int] = (1, 5, 10, 20, 60, 120),
    factor_column: str = "zscore",
) -> pd.DataFrame:
    """Return IC summary ordered by holding-period horizon."""
    required_periods = tuple(int(period) for period in periods)
    available = [
        period for period in required_periods if f"forward_return_{period}d" in evaluation_input.columns
    ]
    if not available:
        available = list(DEFAULT_PERIODS)
    ic = calculate_ic_timeseries(evaluation_input, periods=available, factor_column=factor_column)
    return summarize_ic(ic).sort_values(["market", "period"]).reset_index(drop=True)
