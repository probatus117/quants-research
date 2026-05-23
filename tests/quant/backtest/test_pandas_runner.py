from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.backtest.cost_model import CostConfig
from src.quant.backtest.pandas_runner import BacktestConfig, run_topn_backtest


def _daily_bar() -> pd.DataFrame:
    prices = {
        "2024-01-02": {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0},
        "2024-01-03": {"AAA": 110.0, "BBB": 100.0, "CCC": 90.0},
        "2024-02-01": {"AAA": 120.0, "BBB": 100.0, "CCC": 80.0},
        "2024-02-02": {"AAA": 120.0, "BBB": 100.0, "CCC": 80.0},
    }
    rows = []
    for date, by_symbol in prices.items():
        for symbol, price in by_symbol.items():
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "adj_close": price,
                    "is_suspended": False,
                }
            )
    return pd.DataFrame(rows)


def _signal() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "AAA", "score": 3.0},
            {"date": "2024-01-02", "symbol": "BBB", "score": 2.0},
            {"date": "2024-01-02", "symbol": "CCC", "score": 1.0},
            {"date": "2024-02-01", "symbol": "BBB", "score": 3.0},
            {"date": "2024-02-01", "symbol": "AAA", "score": 2.0},
            {"date": "2024-02-01", "symbol": "CCC", "score": 1.0},
        ]
    )


def test_run_topn_backtest_monthly_equal_weight_without_costs() -> None:
    result = run_topn_backtest(
        _signal(),
        _daily_bar(),
        BacktestConfig(top_n=1, initial_capital=1_000, cost=CostConfig(buy_cost=0, sell_cost=0, min_cost=0)),
    )

    values = result.portfolio_value.set_index("date")["portfolio_value"]
    assert np.isclose(values.loc["2024-01-02"], 1_000)
    assert np.isclose(values.loc["2024-01-03"], 1_100)
    assert np.isclose(values.loc["2024-02-01"], 1_200)
    assert np.isclose(values.loc["2024-02-02"], 1_200)
    assert result.portfolio_value["market"].unique().tolist() == ["cn"]
    assert result.portfolio_value["base_currency"].unique().tolist() == ["CNY"]
    assert result.portfolio_value["benchmark"].unique().tolist() == ["equal_weight"]
    assert result.positions.groupby("date")["symbol"].first().to_dict() == {
        "2024-01-02": "AAA",
        "2024-02-01": "BBB",
    }
    assert set(result.trades["side"]) == {"buy", "sell"}


def test_run_topn_backtest_filters_suspended_names() -> None:
    bars = _daily_bar()
    bars.loc[(bars["date"] == "2024-01-02") & (bars["symbol"] == "AAA"), "is_suspended"] = True

    result = run_topn_backtest(
        _signal(),
        bars,
        BacktestConfig(top_n=1, initial_capital=1_000, cost=CostConfig(buy_cost=0, sell_cost=0, min_cost=0)),
    )

    first_position = result.positions[result.positions["date"] == "2024-01-02"].iloc[0]
    assert first_position["symbol"] == "BBB"
