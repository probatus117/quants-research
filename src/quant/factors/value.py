"""Value factor implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.base import BaseFactor, FactorResult


class ValueBPFactor(BaseFactor):
    """Book-to-price factor: value_bp = 1 / PB."""

    factor_name = "value_bp"
    direction = 1
    required_columns = ("date", "symbol", "pb")

    def compute(self, df: pd.DataFrame) -> FactorResult:
        data = self.validate_input(df).copy()
        pb = pd.to_numeric(data["pb"], errors="coerce")
        data["raw_value"] = np.where(pb > 0, 1.0 / pb, np.nan)
        return self.build_result(data)
