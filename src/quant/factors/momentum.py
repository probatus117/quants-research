"""Momentum factor implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.factors.base import BaseFactor, FactorResult


class Momentum121Factor(BaseFactor):
    """12-1 momentum: adj_close[t-21] / adj_close[t-252] - 1."""

    factor_name = "momentum_12_1"
    direction = 1
    required_columns = ("date", "symbol", "adj_close")

    def compute(self, df: pd.DataFrame) -> FactorResult:
        data = self.validate_input(df).copy()
        data["adj_close"] = pd.to_numeric(data["adj_close"], errors="coerce")
        data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
        grouped = data.groupby("symbol", sort=False)["adj_close"]
        lag_21 = grouped.shift(21)
        lag_252 = grouped.shift(252)
        raw = (lag_21 / lag_252) - 1.0
        data["raw_value"] = raw.where((lag_21 > 0) & (lag_252 > 0), np.nan)
        return self.build_result(data)
