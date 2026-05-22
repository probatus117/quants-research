"""Export quant factor evaluation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.quant.evaluation.minimal_runner import MinimalEvaluationResult


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    return value


def export_evaluation(result: MinimalEvaluationResult, output_dir: str | Path) -> dict[str, Path]:
    """Write JSON/CSV artifacts for a minimal factor evaluation."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "factor_summary": root / "factor_summary.json",
        "ic_timeseries": root / "ic_timeseries.csv",
        "quantile_returns": root / "quantile_returns.csv",
        "coverage": root / "coverage.json",
    }
    paths["factor_summary"].write_text(
        json.dumps(_json_ready(result.factor_summary), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result.ic_timeseries.to_csv(paths["ic_timeseries"], index=False)
    result.quantile_returns.to_csv(paths["quantile_returns"], index=False)
    paths["coverage"].write_text(
        json.dumps(_json_ready(result.coverage), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths
