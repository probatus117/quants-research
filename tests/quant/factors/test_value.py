from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.value import ValueBPFactor


def test_value_bp_computes_inverse_pb() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "symbol": ["000001", "000002"],
            "pb": [0.5, 2.0],
        }
    )

    result = ValueBPFactor().compute(df)

    assert result.values["raw_value"].tolist() == [2.0, 0.5]


def test_value_bp_sets_non_positive_and_missing_pb_to_nan() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02"] * 4,
            "symbol": ["000001", "000002", "000003", "000004"],
            "pb": [1.0, 0.0, -1.5, np.nan],
        }
    )

    result = ValueBPFactor().compute(df)

    assert result.values.loc[0, "raw_value"] == 1.0
    assert result.values.loc[1:, "raw_value"].isna().all()
