from __future__ import annotations

import pandas as pd

from src.quant.backtest.cost_model import default_cost_config
from src.quant.backtest.pandas_runner import BacktestConfig, run_topn_backtest
from src.quant.backtest.walk_forward import walk_forward_metrics


def _bars() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=70)
    rows = []
    for symbol, offset in [("A", 0.1), ("B", 0.2), ("C", 0.3)]:
        for idx, date in enumerate(dates):
            close = 10 + idx * offset
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "market": "us",
                    "symbol": symbol,
                    "adj_close": close,
                    "is_suspended": False,
                }
            )
    return pd.DataFrame(rows)


def _signal() -> pd.DataFrame:
    rows = []
    for date in pd.bdate_range("2024-01-01", periods=70):
        for symbol, score in [("A", 1.0), ("B", 2.0), ("C", 3.0)]:
            rows.append({"date": date.date().isoformat(), "market": "us", "symbol": symbol, "score": score})
    return pd.DataFrame(rows)


def test_weekly_and_quarterly_rebalance_supported() -> None:
    weekly = run_topn_backtest(_signal(), _bars(), BacktestConfig(market="us", base_currency="USD", frequency="weekly", top_n=1))
    quarterly = run_topn_backtest(_signal(), _bars(), BacktestConfig(market="us", base_currency="USD", frequency="quarterly", top_n=1))

    assert int(weekly.portfolio_value["is_rebalance"].sum()) > int(quarterly.portfolio_value["is_rebalance"].sum())
    assert weekly.portfolio_value["base_currency"].eq("USD").all()


def test_market_default_cost_config() -> None:
    assert default_cost_config("us").min_cost == 0
    assert default_cost_config("jp").buy_cost == 0.001


def test_walk_forward_metrics_outputs_windows() -> None:
    result = run_topn_backtest(_signal(), _bars(), BacktestConfig(market="us", base_currency="USD", frequency="monthly", top_n=1))
    windows = walk_forward_metrics(result.portfolio_value, window_days=20, step_days=10)

    assert not windows.empty
    assert {"sharpe", "max_drawdown", "excess_return"}.issubset(windows.columns)
