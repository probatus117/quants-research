"""Transaction cost helpers for the pandas TopN backtest."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.quant.data.market_config import get_market_config


@dataclass(frozen=True)
class CostConfig:
    """Buy/sell cost rates and minimum per-order fee."""

    market: str = "cn"
    buy_cost: float = 0.0015
    sell_cost: float = 0.0025
    min_cost: float = 5.0


def default_cost_config(market: str = "cn") -> CostConfig:
    """Return the default transaction cost model for a market."""
    cfg = get_market_config(market)
    return CostConfig(
        market=cfg.market,
        buy_cost=cfg.buy_cost,
        sell_cost=cfg.sell_cost,
        min_cost=cfg.min_cost,
    )


def calculate_trade_cost(notional: float, side: str, config: CostConfig | None = None) -> float:
    """Calculate cost for a single trade notional."""
    cfg = config or CostConfig()
    amount = abs(float(notional))
    if amount == 0:
        return 0.0
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    rate = cfg.buy_cost if side == "buy" else cfg.sell_cost
    return max(amount * rate, cfg.min_cost)


def build_rebalance_trades(
    previous_weights: dict[str, float],
    target_weights: dict[str, float],
    portfolio_value: float,
    trade_date: object,
    config: CostConfig | None = None,
) -> pd.DataFrame:
    """Build one row per changed symbol, including notional and transaction cost."""
    rows: list[dict[str, object]] = []
    symbols = sorted(set(previous_weights) | set(target_weights))
    for symbol in symbols:
        previous_weight = float(previous_weights.get(symbol, 0.0))
        target_weight = float(target_weights.get(symbol, 0.0))
        delta_weight = target_weight - previous_weight
        if abs(delta_weight) < 1e-12:
            continue
        side = "buy" if delta_weight > 0 else "sell"
        notional = abs(delta_weight) * float(portfolio_value)
        rows.append(
            {
                "date": trade_date,
                "symbol": symbol,
                "side": side,
                "previous_weight": previous_weight,
                "target_weight": target_weight,
                "delta_weight": delta_weight,
                "notional": notional,
                "cost": calculate_trade_cost(notional, side, config),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "date",
            "symbol",
            "side",
            "previous_weight",
            "target_weight",
            "delta_weight",
            "notional",
            "cost",
        ],
    )


def total_trade_cost(trades: pd.DataFrame) -> float:
    """Return total cost for a trade frame."""
    if trades.empty:
        return 0.0
    return float(trades["cost"].sum())
