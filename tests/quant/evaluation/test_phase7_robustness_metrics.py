from __future__ import annotations

import pandas as pd
import numpy as np

from src.quant.evaluation.factor_correlation import factor_correlation_matrix
from src.quant.evaluation.ic_decay import calculate_ic_decay


def _evaluation_input() -> pd.DataFrame:
    rows = []
    for date in pd.bdate_range("2024-01-01", periods=6):
        for idx, symbol in enumerate(["A", "B", "C", "D"]):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "market": "us",
                    "symbol": symbol,
                    "zscore": float(idx),
                    "forward_return_1d": idx * 0.01,
                    "forward_return_5d": idx * 0.02,
                    "forward_return_10d": idx * 0.03,
                }
            )
    return pd.DataFrame(rows)


def test_ic_decay_uses_available_periods() -> None:
    decay = calculate_ic_decay(_evaluation_input(), periods=[1, 5, 10, 20])

    assert decay["period"].tolist() == [1, 5, 10]
    assert decay["rank_ic_mean"].eq(1.0).all()


def test_factor_correlation_matrix_by_market() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 6,
            "market": ["us"] * 6,
            "symbol": ["A", "B", "C", "A", "B", "C"],
            "factor_name": ["f1", "f1", "f1", "f2", "f2", "f2"],
            "zscore": [1.0, 2.0, 3.0, 2.0, 4.0, 6.0],
        }
    )

    corr = factor_correlation_matrix(frame)
    value = corr[(corr["factor_left"] == "f1") & (corr["factor_right"] == "f2")]["correlation"].iloc[0]

    assert np.isclose(value, 1.0)
