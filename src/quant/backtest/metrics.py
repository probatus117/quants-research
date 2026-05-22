"""Backtest performance metrics."""

from __future__ import annotations

import math

import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    """Return max drawdown as a negative decimal."""
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def calculate_metrics(portfolio_value: pd.DataFrame, periods_per_year: int = 252) -> dict[str, float]:
    """Calculate return, risk, turnover, and benchmark metrics."""
    required = {"portfolio_value", "daily_return", "benchmark_value", "turnover"}
    missing = sorted(required - set(portfolio_value.columns))
    if missing:
        raise ValueError(f"portfolio_value missing columns: {', '.join(missing)}")
    if portfolio_value.empty:
        raise ValueError("portfolio_value is empty")

    equity = portfolio_value["portfolio_value"].astype(float)
    returns = portfolio_value["daily_return"].astype(float)
    benchmark = portfolio_value["benchmark_value"].astype(float)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    benchmark_return = float(benchmark.iloc[-1] / benchmark.iloc[0] - 1.0)
    years = max((len(equity) - 1) / periods_per_year, 1 / periods_per_year)
    annual_return = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0)
    daily_std = float(returns.std(ddof=1))
    annual_volatility = daily_std * math.sqrt(periods_per_year) if not math.isnan(daily_std) else 0.0
    sharpe = (
        float(returns.mean() / daily_std * math.sqrt(periods_per_year))
        if daily_std and not math.isnan(daily_std)
        else 0.0
    )
    mdd = max_drawdown(equity)
    calmar = annual_return / abs(mdd) if mdd < 0 else 0.0
    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": calmar,
        "turnover": float(portfolio_value["turnover"].sum()),
        "average_turnover": float(portfolio_value["turnover"].mean()),
        "benchmark_return": benchmark_return,
        "excess_return": total_return - benchmark_return,
        "final_value": float(equity.iloc[-1]),
    }
