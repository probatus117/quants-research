"""Low-volatility factor implementations."""

from __future__ import annotations

import pandas as pd

from src.quant.factors.base import BaseFactor, FactorResult


class LowVolatility60DFactor(BaseFactor):
    """Low volatility factor: negative 60-day standard deviation of daily returns."""

    factor_name = "lowvol_60d"
    direction = 1
    required_columns = ("date", "symbol", "adj_close")

    def compute(self, df: pd.DataFrame) -> FactorResult:
        data = self.validate_input(df).copy()
        data["adj_close"] = pd.to_numeric(data["adj_close"], errors="coerce")
        data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
        returns = data.groupby("symbol", sort=False)["adj_close"].pct_change()
        vol = returns.groupby(data["symbol"], sort=False).rolling(60, min_periods=60).std()
        data["raw_value"] = -vol.reset_index(level=0, drop=True)
        return self.build_result(data)
