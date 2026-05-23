"""Market-level defaults for Phase 7 multi-market quant research."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketConfig:
    """Static configuration shared by providers, factors, and backtests."""

    market: str
    currency: str
    exchanges: tuple[str, ...]
    benchmark: str
    benchmark_symbol: str
    timezone: str
    buy_cost: float
    sell_cost: float
    min_cost: float
    momentum_lookback_days: int = 252
    momentum_skip_days: int = 21
    lowvol_window_days: int = 60
    weekly_rule: str = "W-MON"
    quarterly_rule: str = "Q"


MARKET_CONFIGS: dict[str, MarketConfig] = {
    "cn": MarketConfig(
        market="cn",
        currency="CNY",
        exchanges=("SH", "SZ"),
        benchmark="csi300",
        benchmark_symbol="000300.SS",
        timezone="Asia/Shanghai",
        buy_cost=0.0015,
        sell_cost=0.0025,
        min_cost=5.0,
    ),
    "us": MarketConfig(
        market="us",
        currency="USD",
        exchanges=("NYSE", "NASDAQ"),
        benchmark="sp500",
        benchmark_symbol="^GSPC",
        timezone="America/New_York",
        buy_cost=0.00002,
        sell_cost=0.00002,
        min_cost=0.0,
    ),
    "jp": MarketConfig(
        market="jp",
        currency="JPY",
        exchanges=("TSE",),
        benchmark="nikkei225",
        benchmark_symbol="^N225",
        timezone="Asia/Tokyo",
        buy_cost=0.001,
        sell_cost=0.001,
        min_cost=0.0,
    ),
}


def normalize_market(market: str | None) -> str:
    """Normalize and validate a market code."""
    code = (market or "cn").strip().lower()
    if code not in MARKET_CONFIGS:
        raise ValueError(f"Unsupported quant market: {market!r}")
    return code


def get_market_config(market: str | None = None) -> MarketConfig:
    """Return the static config for a supported market."""
    return MARKET_CONFIGS[normalize_market(market)]


def market_codes() -> tuple[str, ...]:
    """Return supported market codes in deterministic order."""
    return tuple(MARKET_CONFIGS)
