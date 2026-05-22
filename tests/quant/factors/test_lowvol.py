from __future__ import annotations

import pandas as pd

from src.quant.factors.low_volatility import LowVolatility60DFactor


def test_lowvol_60d_is_negative_rolling_return_std() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70).strftime("%Y-%m-%d")
    prices = [100.0]
    for i in range(1, 70):
        prices.append(prices[-1] * (1.0 + (0.01 if i % 2 else -0.005)))
    df = pd.DataFrame({"date": dates, "symbol": "000001", "adj_close": prices})

    result = LowVolatility60DFactor().compute(df)
    expected = -pd.Series(prices).pct_change().rolling(60, min_periods=60).std().iloc[60]

    assert result.values.loc[60, "raw_value"] == expected
    assert result.values.loc[:59, "raw_value"].isna().all()


def test_lowvol_60d_scores_lower_volatility_higher() -> None:
    dates = pd.bdate_range("2024-01-02", periods=70).strftime("%Y-%m-%d")
    low_prices = [100.0]
    high_prices = [100.0]
    for i in range(1, 70):
        low_prices.append(low_prices[-1] * 1.001)
        high_prices.append(high_prices[-1] * (1.03 if i % 2 else 0.97))
    df = pd.concat(
        [
            pd.DataFrame({"date": dates, "symbol": "LOW", "adj_close": low_prices}),
            pd.DataFrame({"date": dates, "symbol": "HIGH", "adj_close": high_prices}),
        ],
        ignore_index=True,
    )

    result = LowVolatility60DFactor().compute(df)
    latest = result.values[result.values["date"] == dates[-1]].set_index("symbol")

    assert latest.loc["LOW", "raw_value"] > latest.loc["HIGH", "raw_value"]


def test_lowvol_60d_marks_insufficient_history_as_nan() -> None:
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=30).strftime("%Y-%m-%d"),
            "symbol": "000001",
            "adj_close": [100.0 + i for i in range(30)],
        }
    )

    result = LowVolatility60DFactor().compute(df)

    assert result.values["raw_value"].isna().all()
