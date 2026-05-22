"""Markdown report generation for pandas TopN backtests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _pct(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def write_backtest_report(
    metrics: dict[str, Any],
    config: dict[str, Any],
    artifact_paths: dict[str, str],
    output_path: str | Path,
) -> Path:
    """Write a compact Markdown report using metrics/artifact inputs."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Quant Backtest Report",
        "",
        "## Strategy Parameters",
        "",
        f"- signal: `{config.get('signal_name', 'unknown')}`",
        f"- frequency: `{config.get('frequency', 'monthly')}`",
        f"- top_n: `{config.get('top_n', 'n/a')}`",
        f"- weight: `equal`",
        f"- initial_capital: `{config.get('initial_capital', 'n/a')}`",
        f"- cost: buy `{config.get('buy_cost', 'n/a')}`, sell `{config.get('sell_cost', 'n/a')}`, min `{config.get('min_cost', 'n/a')}`",
        "",
        "## Return Metrics",
        "",
        f"- total_return: {_pct(metrics.get('total_return'))}",
        f"- annual_return: {_pct(metrics.get('annual_return'))}",
        f"- benchmark_return: {_pct(metrics.get('benchmark_return'))}",
        f"- excess_return: {_pct(metrics.get('excess_return'))}",
        "",
        "## Risk Metrics",
        "",
        f"- annual_volatility: {_pct(metrics.get('annual_volatility'))}",
        f"- sharpe: {float(metrics.get('sharpe', 0.0)):.3f}",
        f"- max_drawdown: {_pct(metrics.get('max_drawdown'))}",
        f"- calmar: {float(metrics.get('calmar', 0.0)):.3f}",
        "",
        "## Trading Metrics",
        "",
        f"- turnover: {float(metrics.get('turnover', 0.0)):.4f}",
        f"- average_turnover: {float(metrics.get('average_turnover', 0.0)):.4f}",
        f"- final_value: {float(metrics.get('final_value', 0.0)):.2f}",
        "",
        "## Artifacts",
        "",
    ]
    for name, artifact_path in sorted(artifact_paths.items()):
        lines.append(f"- {name}: `{artifact_path}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This pandas TopN backtest is an offline research artifact. It is not a trading recommendation.",
            "",
            "## Raw Metrics",
            "",
            "```json",
            json.dumps(metrics, ensure_ascii=True, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
