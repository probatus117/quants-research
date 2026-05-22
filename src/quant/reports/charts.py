"""Chart generation for quant reports."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def _drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def write_backtest_charts(portfolio_value: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    """Write equity, drawdown, and yearly-return charts."""
    chart_dir = Path(output_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(chart_dir / ".matplotlib"))
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        marker = chart_dir / "matplotlib_unavailable.txt"
        marker.write_text("matplotlib is not installed; backtest charts were skipped.\n", encoding="utf-8")
        return {"matplotlib_unavailable": marker}

    df = portfolio_value.copy()
    df["date"] = pd.to_datetime(df["date"])
    paths = {
        "equity_curve": chart_dir / "equity_curve.png",
        "drawdown": chart_dir / "drawdown.png",
        "yearly_return": chart_dir / "yearly_return.png",
    }

    plt.figure(figsize=(9, 4))
    plt.plot(df["date"], df["portfolio_value"], label="Portfolio")
    plt.plot(df["date"], df["benchmark_value"], label="Benchmark", alpha=0.75)
    plt.legend()
    plt.title("Equity Curve")
    plt.tight_layout()
    plt.savefig(paths["equity_curve"])
    plt.close()

    plt.figure(figsize=(9, 4))
    plt.plot(df["date"], _drawdown(df["portfolio_value"]))
    plt.title("Drawdown")
    plt.tight_layout()
    plt.savefig(paths["drawdown"])
    plt.close()

    yearly = df.set_index("date")["portfolio_value"].resample("YE").last().pct_change().dropna()
    if yearly.empty:
        yearly = pd.Series([df["portfolio_value"].iloc[-1] / df["portfolio_value"].iloc[0] - 1.0], index=[df["date"].max()])
    plt.figure(figsize=(9, 4))
    plt.bar([str(index.year) for index in yearly.index], yearly.values)
    plt.title("Yearly Return")
    plt.tight_layout()
    plt.savefig(paths["yearly_return"])
    plt.close()

    return paths
