"""Walk-forward evaluation helpers for backtest metric stability."""

from __future__ import annotations

import pandas as pd

from src.quant.backtest.metrics import calculate_metrics


def walk_forward_metrics(
    portfolio_value: pd.DataFrame,
    window_days: int = 252,
    step_days: int = 63,
    mode: str = "rolling",
) -> pd.DataFrame:
    """Calculate metrics over rolling or expanding windows."""
    if mode not in {"rolling", "expanding"}:
        raise ValueError("mode must be 'rolling' or 'expanding'")
    if window_days <= 1 or step_days <= 0:
        raise ValueError("window_days must be > 1 and step_days must be positive")
    frame = portfolio_value.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for end in range(window_days, len(frame) + 1, step_days):
        start = 0 if mode == "expanding" else end - window_days
        window = frame.iloc[start:end].copy()
        if len(window) < 2:
            continue
        metrics = calculate_metrics(window)
        rows.append(
            {
                "mode": mode,
                "window_start": window["date"].iloc[0].date().isoformat(),
                "window_end": window["date"].iloc[-1].date().isoformat(),
                "observations": int(len(window)),
                "market": metrics.get("market", "unknown"),
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "total_return": metrics["total_return"],
                "excess_return": metrics["excess_return"],
            }
        )
    return pd.DataFrame(rows)
