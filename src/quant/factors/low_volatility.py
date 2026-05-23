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
        group_keys = ["market", "symbol"] if "market" in data.columns else ["symbol"]
        data = data.sort_values([*group_keys, "date"]).reset_index(drop=True)
        window = int(self.config.params.get("window_days", 60))
        returns = data.groupby(group_keys, sort=False)["adj_close"].pct_change()
        group_values = [data[key] for key in group_keys]
        vol = returns.groupby(group_values, sort=False).rolling(window, min_periods=window).std()
        data["raw_value"] = -vol.reset_index(level=list(range(len(group_keys))), drop=True)
        return self.build_result(data)
