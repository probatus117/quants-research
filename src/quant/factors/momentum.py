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
        group_keys = ["market", "symbol"] if "market" in data.columns else ["symbol"]
        data = data.sort_values([*group_keys, "date"]).reset_index(drop=True)
        skip_days = int(self.config.params.get("skip_days", 21))
        lookback_days = int(self.config.params.get("lookback_days", 252))
        grouped = data.groupby(group_keys, sort=False)["adj_close"]
        lag_skip = grouped.shift(skip_days)
        lag_lookback = grouped.shift(lookback_days)
        raw = (lag_skip / lag_lookback) - 1.0
        data["raw_value"] = raw.where((lag_skip > 0) & (lag_lookback > 0), np.nan)
        return self.build_result(data)
