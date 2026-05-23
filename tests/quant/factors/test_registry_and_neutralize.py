from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.processing import neutralize
from src.quant.factors.registry import load_factor_specs


def test_factor_registry_resolves_market_params() -> None:
    specs = {spec.name: spec for spec in load_factor_specs(market="us", names=["momentum_12_1", "lowvol_60d"])}

    assert specs["momentum_12_1"].params == {"lookback_days": 252, "skip_days": 21}
    assert specs["lowvol_60d"].source_table == "daily_bar"


def test_neutralize_removes_industry_and_size_linear_effects() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-02"] * 6,
            "market": ["us"] * 6,
            "factor_name": ["value_bp"] * 6,
            "zscore": [1.0, 1.2, 1.4, 3.0, 3.2, 3.4],
            "industry": ["A", "A", "A", "B", "B", "B"],
            "log_market_cap": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        }
    )

    residual = neutralize(frame)

    assert np.isclose(float(residual.mean()), 0.0, atol=1e-10)
    assert float(residual.abs().max()) < 1e-10
