"""Pandas TopN backtest runner."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.quant.backtest.cost_model import CostConfig, build_rebalance_trades, default_cost_config, total_trade_cost
from src.quant.backtest.strategies import BaseStrategy, TopNEqualWeight


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for the Phase 4 monthly TopN backtest."""

    top_n: int = 10
    market: str = "cn"
    base_currency: str = "CNY"
    benchmark: str = "equal_weight"
    frequency: str = "monthly"
    initial_capital: float = 1_000_000.0
    exclude_st: bool = True
    exclude_suspended: bool = True
    cost: CostConfig = field(default_factory=CostConfig)
    strategy: BaseStrategy = field(default_factory=TopNEqualWeight)


@dataclass(frozen=True)
class BacktestResult:
    """Backtest artifacts produced by the pandas runner."""

    portfolio_value: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame


def _prepare_prices(daily_bar: pd.DataFrame, benchmark: str = "equal_weight") -> pd.DataFrame:
    required = {"date", "symbol", "adj_close"}
    missing = sorted(required - set(daily_bar.columns))
    if missing:
        raise ValueError(f"daily_bar missing columns: {', '.join(missing)}")
    bars = daily_bar.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    if benchmark != "equal_weight" and "is_benchmark" in bars.columns:
        bars = bars[~bars["is_benchmark"]].copy()
    prices = bars.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="first").sort_index()
    if prices.empty:
        raise ValueError("daily_bar produced an empty price matrix")
    return prices


def _monthly_rebalance_dates(dates: pd.DatetimeIndex) -> set[pd.Timestamp]:
    frame = pd.DataFrame({"date": dates})
    return set(frame.groupby(frame["date"].dt.to_period("M"), sort=True)["date"].first())


def _rebalance_dates(dates: pd.DatetimeIndex, frequency: str) -> set[pd.Timestamp]:
    frame = pd.DataFrame({"date": dates})
    if frequency == "weekly":
        return set(frame.groupby(frame["date"].dt.to_period("W"), sort=True)["date"].first())
    if frequency == "monthly":
        return _monthly_rebalance_dates(dates)
    if frequency == "quarterly":
        return set(frame.groupby(frame["date"].dt.to_period("Q"), sort=True)["date"].first())
    raise ValueError("frequency must be one of: weekly, monthly, quarterly")


def _signal_for_date(
    signal: pd.DataFrame,
    daily_bar: pd.DataFrame,
    date: pd.Timestamp,
    config: BacktestConfig,
) -> pd.DataFrame:
    day_signal = signal[signal["date"] == date].copy()
    if day_signal.empty:
        return day_signal

    bars = daily_bar[daily_bar["date"] == date].copy()
    filter_columns = ["symbol"]
    if config.exclude_suspended and "is_suspended" in bars.columns:
        bars = bars[~bars["is_suspended"]]
    if config.exclude_st and "is_st" in bars.columns:
        bars = bars[~bars["is_st"]]
    if config.exclude_st and "is_st" in day_signal.columns:
        day_signal = day_signal[~day_signal["is_st"]]
    if config.exclude_st and "name" in day_signal.columns:
        day_signal = day_signal[~day_signal["name"].astype("string").str.contains("ST", na=False)]

    tradable = bars[filter_columns].drop_duplicates()
    day_signal = day_signal.merge(tradable, on="symbol", how="inner")
    return day_signal.dropna(subset=["score"]).sort_values(["score", "symbol"], ascending=[False, True])


def _target_weights(
    day_signal: pd.DataFrame,
    date: pd.Timestamp,
    top_n: int,
    strategy: BaseStrategy,
) -> dict[str, float]:
    selected = strategy.select(day_signal, date, top_n)
    return strategy.weight(selected, day_signal, date)


def _position_rows(
    date: pd.Timestamp,
    weights: dict[str, float],
    prices: pd.Series,
    nav: float,
    config: BacktestConfig,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, weight in sorted(weights.items()):
        price = float(prices.get(symbol, float("nan")))
        market_value = nav * weight
        rows.append(
            {
                "date": date.date().isoformat(),
                "market": config.market,
                "base_currency": config.base_currency,
                "benchmark": config.benchmark,
                "symbol": symbol,
                "weight": weight,
                "price": price,
                "shares": market_value / price if price > 0 else 0.0,
                "market_value": market_value,
            }
        )
    return rows


def _benchmark_series(
    prices: pd.DataFrame,
    initial_capital: float,
    daily_bar: pd.DataFrame | None = None,
    benchmark: str = "equal_weight",
) -> pd.DataFrame:
    if benchmark != "equal_weight" and daily_bar is not None:
        bars = daily_bar.copy()
        bars["date"] = pd.to_datetime(bars["date"])
        benchmark_mask = bars["symbol"].astype(str).eq(benchmark)
        if "is_benchmark" in bars.columns:
            benchmark_mask = benchmark_mask | bars["is_benchmark"].astype(bool)
        benchmark_bars = bars[benchmark_mask].sort_values("date")
        if not benchmark_bars.empty:
            series = benchmark_bars.set_index("date")["adj_close"].astype(float).reindex(prices.index).ffill()
            benchmark_return = series.pct_change().fillna(0.0)
            benchmark_value = initial_capital * (1.0 + benchmark_return).cumprod()
            return pd.DataFrame({"benchmark_return": benchmark_return, "benchmark_value": benchmark_value})
    returns = prices.pct_change().fillna(0.0)
    benchmark_return = returns.mean(axis=1, skipna=True).fillna(0.0)
    benchmark_value = initial_capital * (1.0 + benchmark_return).cumprod()
    return pd.DataFrame({"benchmark_return": benchmark_return, "benchmark_value": benchmark_value})


def run_topn_backtest(
    signal: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a deterministic monthly TopN equal-weight backtest."""
    cfg = config or BacktestConfig()
    if cfg.top_n <= 0:
        raise ValueError("top_n must be positive")
    required_signal = {"date", "symbol", "score"}
    missing = sorted(required_signal - set(signal.columns))
    if missing:
        raise ValueError(f"signal missing columns: {', '.join(missing)}")

    bars = daily_bar.copy()
    if "market" in bars.columns:
        bars = bars[bars["market"] == cfg.market].copy()
    prices = _prepare_prices(bars, cfg.benchmark)
    bars["date"] = pd.to_datetime(bars["date"])
    sig = signal.copy()
    if "market" in sig.columns:
        sig = sig[sig["market"] == cfg.market].copy()
    sig["date"] = pd.to_datetime(sig["date"])
    sig = sig[sig["date"].isin(prices.index)]
    rebalance_dates = _rebalance_dates(prices.index, cfg.frequency)
    benchmark = _benchmark_series(prices, cfg.initial_capital, bars, cfg.benchmark)
    cost_config = (
        default_cost_config(cfg.market)
        if cfg.cost == CostConfig() and cfg.market != cfg.cost.market
        else cfg.cost
    )

    nav = float(cfg.initial_capital)
    weights: dict[str, float] = {}
    portfolio_rows: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []
    trade_frames: list[pd.DataFrame] = []
    previous_date: pd.Timestamp | None = None
    previous_nav = nav

    for date in prices.index:
        gross_return = 0.0
        if previous_date is not None and weights:
            day_returns = prices.loc[date] / prices.loc[previous_date] - 1.0
            gross_return = float(sum(weights.get(symbol, 0.0) * day_returns.get(symbol, 0.0) for symbol in weights))
            nav *= 1.0 + gross_return

        cost = 0.0
        turnover = 0.0
        is_rebalance = date in rebalance_dates
        if is_rebalance:
            day_signal = _signal_for_date(sig, bars, date, cfg)
            target = _target_weights(day_signal, date, cfg.top_n, cfg.strategy)
            trades = build_rebalance_trades(weights, target, nav, date.date().isoformat(), cost_config)
            cost = total_trade_cost(trades)
            turnover = float(trades["delta_weight"].abs().sum()) if not trades.empty else 0.0
            nav -= cost
            if not trades.empty:
                trades["market"] = cfg.market
                trades["base_currency"] = cfg.base_currency
                trades["benchmark"] = cfg.benchmark
                trade_frames.append(trades)
            weights = target
            position_rows.extend(_position_rows(date, weights, prices.loc[date], nav, cfg))

        daily_return = nav / previous_nav - 1.0 if previous_nav else 0.0
        portfolio_rows.append(
            {
                "date": date.date().isoformat(),
                "market": cfg.market,
                "base_currency": cfg.base_currency,
                "benchmark": cfg.benchmark,
                "portfolio_value": nav,
                "daily_return": daily_return,
                "gross_return": gross_return,
                "cost": cost,
                "turnover": turnover,
                "is_rebalance": is_rebalance,
                "benchmark_value": float(benchmark.loc[date, "benchmark_value"]),
                "benchmark_return": float(benchmark.loc[date, "benchmark_return"]),
            }
        )
        previous_nav = nav
        previous_date = date

    trades = (
        pd.concat(trade_frames, ignore_index=True)
        if trade_frames
        else pd.DataFrame(
            columns=[
                "date",
                "market",
                "base_currency",
                "benchmark",
                "symbol",
                "side",
                "previous_weight",
                "target_weight",
                "delta_weight",
                "notional",
                "cost",
            ]
        )
    )
    return BacktestResult(
        portfolio_value=pd.DataFrame(portfolio_rows),
        positions=pd.DataFrame(
            position_rows,
            columns=[
                "date",
                "market",
                "base_currency",
                "benchmark",
                "symbol",
                "weight",
                "price",
                "shares",
                "market_value",
            ],
        ),
        trades=trades,
    )
