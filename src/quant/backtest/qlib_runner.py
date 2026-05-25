"""Optional Qlib compatibility backtest adapter and pandas comparison report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.backtest.metrics import calculate_metrics
from src.quant.backtest.pandas_runner import BacktestConfig, BacktestResult, run_topn_backtest
from src.quant.data.qlib_converter import QLIB_SKIP_REASON, check_qlib_capability


@dataclass(frozen=True)
class QlibBacktestResult:
    """Audit payload for Qlib or skipped execution."""

    available: bool
    fallback_used: bool
    skip_reason: str | None
    artifacts: dict[str, str]
    metrics: dict[str, Any]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "qlib_runner",
            "runner_type": "compatibility runner",
            "available": self.available,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }


def run_qlib_backtest(
    signal: pd.DataFrame,
    daily_bar: pd.DataFrame,
    config: BacktestConfig | None = None,
    output_dir: str | Path = "data/quant/backtest/qlib",
    enabled: bool = True,
) -> QlibBacktestResult:
    """Run Qlib when installed; otherwise write an audited skip marker.

    This compatibility runner preserves the Phase 7.10 artifact contract by
    using the pandas engine behind a Qlib availability gate. Native Qlib
    Alpha158/LightGBM/backtest execution lives in qlib_native_runner.py.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "qlib_run_summary.json"
    capability = check_qlib_capability()
    if not enabled or not capability.available:
        reason = "qlib disabled by caller; qlib backtest skipped" if not enabled else capability.skip_reason
        result = QlibBacktestResult(
            available=False,
            fallback_used=True,
            skip_reason=reason or QLIB_SKIP_REASON,
            artifacts={"summary": str(summary_path)},
            metrics={},
        )
        summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    cfg = config or BacktestConfig()
    pandas_result: BacktestResult = run_topn_backtest(signal, daily_bar, cfg)
    portfolio_path = output / "portfolio_value.csv"
    positions_path = output / "positions.csv"
    trades_path = output / "trades.csv"
    metrics_path = output / "metrics.json"
    pandas_result.portfolio_value.to_csv(portfolio_path, index=False)
    pandas_result.positions.to_csv(positions_path, index=False)
    pandas_result.trades.to_csv(trades_path, index=False)
    metrics = calculate_metrics(pandas_result.portfolio_value)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = QlibBacktestResult(
        available=True,
        fallback_used=False,
        skip_reason=None,
        artifacts={
            "portfolio_value": str(portfolio_path),
            "positions": str(positions_path),
            "trades": str(trades_path),
            "metrics": str(metrics_path),
            "summary": str(summary_path),
        },
        metrics=metrics,
    )
    summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def write_qlib_vs_pandas_comparison(
    qlib_metrics: dict[str, Any],
    pandas_metrics: dict[str, Any],
    output_path: str | Path = "data/quant/backtest/qlib_vs_pandas_comparison.md",
    same_strategy: bool = True,
) -> Path:
    """Write an auditable Qlib-vs-pandas metric comparison."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = ["annual_return", "sharpe", "max_drawdown"]
    lines = [
        "# Qlib vs Pandas Comparison",
        "",
        f"- same_strategy: `{same_strategy}`",
        "",
        "| metric | pandas | qlib | delta |",
        "|---|---:|---:|---:|",
    ]
    for key in keys:
        left = pandas_metrics.get(key)
        right = qlib_metrics.get(key)
        delta = float(right) - float(left) if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None
        lines.append(f"| `{key}` | {left} | {right} | {delta} |")
    if not same_strategy:
        lines.extend(
            [
                "",
                "The two runs use different strategy semantics or cost assumptions; deltas are descriptive only.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
