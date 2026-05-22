from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.momentum import Momentum121Factor


def _price_frame(symbol: str = "000001", periods: int = 260) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2023-01-02", periods=periods).strftime("%Y-%m-%d"),
            "symbol": symbol,
            "adj_close": [100.0 + i for i in range(periods)],
        }
    )


def test_momentum_12_1_uses_21_and_252_day_lags() -> None:
    df = _price_frame()

    result = Momentum121Factor().compute(df)

    expected = df.loc[252 - 21, "adj_close"] / df.loc[0, "adj_close"] - 1.0
    assert result.values.loc[252, "raw_value"] == expected
    assert result.values.loc[:251, "raw_value"].isna().all()


def test_momentum_12_1_marks_insufficient_history_as_nan() -> None:
    result = Momentum121Factor().compute(_price_frame(periods=100))

    assert result.values["raw_value"].isna().all()


def test_momentum_12_1_handles_missing_lag_prices_as_nan() -> None:
    df = _price_frame(periods=260)
    df.loc[231, "adj_close"] = np.nan

    result = Momentum121Factor().compute(df)

    assert pd.isna(result.values.loc[252, "raw_value"])
