from __future__ import annotations

import numpy as np

from src.quant.backtest.cost_model import CostConfig, build_rebalance_trades, calculate_trade_cost, total_trade_cost


def test_calculate_trade_cost_applies_side_rates_and_minimum() -> None:
    config = CostConfig(buy_cost=0.0015, sell_cost=0.0025, min_cost=5)

    assert calculate_trade_cost(10_000, "buy", config) == 15
    assert calculate_trade_cost(10_000, "sell", config) == 25
    assert calculate_trade_cost(100, "buy", config) == 5


def test_build_rebalance_trades_from_weight_deltas() -> None:
    trades = build_rebalance_trades(
        previous_weights={"AAA": 0.5, "BBB": 0.5},
        target_weights={"AAA": 1.0},
        portfolio_value=10_000,
        trade_date="2024-01-02",
        config=CostConfig(min_cost=0),
    )

    by_symbol = trades.set_index("symbol")
    assert by_symbol.loc["AAA", "side"] == "buy"
    assert by_symbol.loc["BBB", "side"] == "sell"
    assert np.isclose(by_symbol.loc["AAA", "notional"], 5_000)
    assert np.isclose(total_trade_cost(trades), 20.0)
