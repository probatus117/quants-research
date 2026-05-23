from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.backtest.metrics import calculate_metrics, max_drawdown


def test_max_drawdown_uses_running_peak() -> None:
    equity = pd.Series([100.0, 120.0, 90.0, 135.0])

    assert np.isclose(max_drawdown(equity), -0.25)


def test_calculate_metrics_known_series() -> None:
    portfolio = pd.DataFrame(
        {
            "portfolio_value": [100.0, 110.0, 105.0, 120.0],
            "daily_return": [0.0, 0.10, -0.0454545455, 0.1428571429],
            "benchmark_value": [100.0, 105.0, 105.0, 110.0],
            "turnover": [1.0, 0.0, 0.5, 0.0],
        }
    )

    metrics = calculate_metrics(portfolio, periods_per_year=252)

    assert np.isclose(metrics["total_return"], 0.20)
    assert np.isclose(metrics["benchmark_return"], 0.10)
    assert np.isclose(metrics["excess_return"], 0.10)
    assert np.isclose(metrics["max_drawdown"], 105.0 / 110.0 - 1.0)
    assert np.isclose(metrics["turnover"], 1.5)
    assert metrics["annual_volatility"] > 0
