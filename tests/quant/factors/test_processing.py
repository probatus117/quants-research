from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.processing import process_factor_values, rank_percentile, winsorize_mad, zscore


def test_winsorize_mad_clips_extreme_values() -> None:
    series = pd.Series([1.0, 1.1, 0.9, 1.0, 100.0])

    clipped = winsorize_mad(series, n=3)

    assert clipped.max() < 100.0
    assert clipped.iloc[0] == 1.0


def test_zscore_has_zero_mean_and_unit_sample_std() -> None:
    scores = zscore(pd.Series([1.0, 2.0, 3.0, 4.0]))

    assert np.isclose(scores.mean(), 0.0)
    assert np.isclose(scores.std(), 1.0)


def test_rank_percentile_range_and_direction() -> None:
    series = pd.Series([1.0, 2.0, 3.0])

    positive = rank_percentile(series, direction=1)
    negative = rank_percentile(series, direction=-1)

    assert positive.tolist() == [1 / 3, 2 / 3, 1.0]
    assert negative.tolist() == [1.0, 2 / 3, 1 / 3]


def test_process_factor_values_adds_cross_sectional_columns() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02"] * 3,
            "symbol": ["000001", "000002", "000003"],
            "factor_name": ["value_bp"] * 3,
            "raw_value": [1.0, 2.0, 3.0],
            "direction": [1, 1, 1],
            "universe": ["sample_a"] * 3,
        }
    )

    processed = process_factor_values(df)

    assert set(["winsorized_value", "zscore", "percentile", "zscore_neutral"]).issubset(processed.columns)
    assert np.isclose(processed["zscore"].mean(), 0.0)
    assert np.isclose(processed["zscore"].std(), 1.0)
    assert processed["percentile"].between(0, 1).all()
