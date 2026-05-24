"""Optional vectorbt adapter for parameter-grid strategy scans."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "stock_skills_matplotlib"))
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

try:  # pragma: no cover - environment-specific.
    import vectorbt as vbt

    HAS_VECTORBT = True
    VECTORBT_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    vbt = None
    HAS_VECTORBT = False
    VECTORBT_IMPORT_ERROR = exc


VECTORBT_SKIP_REASON = "vectorbt is not installed; parameter grid experiment skipped"


@dataclass(frozen=True)
class VectorbtCapability:
    """Runtime availability for the optional vectorbt integration."""

    available: bool
    skip_reason: str | None = None


@dataclass(frozen=True)
class VectorbtGridResult:
    """Audit payload for vectorbt grid runs or skips."""

    available: bool
    fallback_used: bool
    skip_reason: str | None
    artifacts: dict[str, str]
    ranking: pd.DataFrame

    def to_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "vectorbt_runner",
            "available": self.available,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "artifacts": self.artifacts,
            "ranking_rows": int(len(self.ranking)),
        }


def check_vectorbt_capability() -> VectorbtCapability:
    """Return vectorbt availability without making it a hard dependency."""

    if HAS_VECTORBT and vbt is not None:
        return VectorbtCapability(available=True)
    if VECTORBT_IMPORT_ERROR is not None:
        return VectorbtCapability(available=False, skip_reason=f"vectorbt import failed: {VECTORBT_IMPORT_ERROR}; parameter grid experiment skipped")
    return VectorbtCapability(available=False, skip_reason=VECTORBT_SKIP_REASON)


def _price_matrix(daily_bar: pd.DataFrame) -> pd.DataFrame:
    bars = daily_bar.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    if "market" not in bars.columns:
        bars["market"] = "unknown"
    bars["asset"] = bars["market"].astype(str) + ":" + bars["symbol"].astype(str)
    return bars.pivot_table(index="date", columns="asset", values="adj_close", aggfunc="first").sort_index().ffill()


def _write_skip(output: Path, reason: str) -> VectorbtGridResult:
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "vectorbt_summary.json"
    result = VectorbtGridResult(
        available=False,
        fallback_used=True,
        skip_reason=reason,
        artifacts={"summary": str(summary_path)},
        ranking=pd.DataFrame(columns=["fast_window", "slow_window", "total_return", "sharpe"]),
    )
    summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _fallback_grid_metrics(close: pd.DataFrame, entries: pd.DataFrame) -> tuple[float, float]:
    returns = close.pct_change().fillna(0.0)
    shifted = entries.shift(1)
    active = shifted.where(shifted.notna(), False).astype(bool)
    strategy_returns = returns.where(active, 0.0).mean(axis=1)
    total_return = float((1.0 + strategy_returns).prod() - 1.0)
    std = float(strategy_returns.std(ddof=1))
    sharpe = float(strategy_returns.mean() / std * (252 ** 0.5)) if std else 0.0
    return total_return, sharpe


def run_vectorbt_grid(
    daily_bar: pd.DataFrame,
    fast_windows: tuple[int, ...] = (5, 10),
    slow_windows: tuple[int, ...] = (20, 60),
    output_dir: str | Path = "data/quant/backtest/vectorbt_grid",
    enabled: bool = True,
) -> VectorbtGridResult:
    """Run an SMA crossover parameter grid for ETF-style price data."""

    output = Path(output_dir)
    capability = check_vectorbt_capability()
    if not enabled:
        return _write_skip(output, "vectorbt disabled by caller; parameter grid experiment skipped")
    if not capability.available or vbt is None:
        return _write_skip(output, capability.skip_reason or VECTORBT_SKIP_REASON)

    output.mkdir(parents=True, exist_ok=True)
    close = _price_matrix(daily_bar)
    rows: list[dict[str, float | int]] = []
    for fast, slow in product(fast_windows, slow_windows):
        if fast >= slow:
            continue
        fast_ma = close.rolling(fast).mean()
        slow_ma = close.rolling(slow).mean()
        entries = fast_ma > slow_ma
        exits = fast_ma < slow_ma
        portfolio = vbt.Portfolio.from_signals(close, entries, exits, init_cash=100_000.0, fees=0.0002)
        try:
            total_return = portfolio.total_return()
            sharpe = portfolio.sharpe_ratio()
            total_return_value = float(total_return.mean() if hasattr(total_return, "mean") else total_return)
            sharpe_value = float(sharpe.mean() if hasattr(sharpe, "mean") else sharpe)
            metric_engine = "vectorbt"
        except Exception:
            total_return_value, sharpe_value = _fallback_grid_metrics(close, entries)
            metric_engine = "pandas_metric_fallback"
        rows.append(
            {
                "fast_window": int(fast),
                "slow_window": int(slow),
                "total_return": total_return_value,
                "sharpe": sharpe_value,
                "metric_engine": metric_engine,
            }
        )
    ranking = pd.DataFrame(rows).sort_values(["sharpe", "total_return"], ascending=[False, False]).reset_index(drop=True)
    ranking_path = output / "ranking.csv"
    ranking.to_csv(ranking_path, index=False)
    heatmap_path = output / "heatmap.png"
    try:
        import matplotlib.pyplot as plt

        pivot = ranking.pivot(index="fast_window", columns="slow_window", values="sharpe")
        plt.figure(figsize=(6, 4))
        plt.imshow(pivot.fillna(0.0), aspect="auto")
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)
        plt.colorbar(label="Sharpe")
        plt.xlabel("slow_window")
        plt.ylabel("fast_window")
        plt.tight_layout()
        plt.savefig(heatmap_path)
        plt.close()
    except ImportError:
        heatmap_path.write_text("matplotlib is not installed; heatmap skipped.\n", encoding="utf-8")
    summary_path = output / "vectorbt_summary.json"
    result = VectorbtGridResult(
        available=True,
        fallback_used=False,
        skip_reason=None,
        artifacts={"ranking": str(ranking_path), "heatmap": str(heatmap_path), "summary": str(summary_path)},
        ranking=ranking,
    )
    summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
