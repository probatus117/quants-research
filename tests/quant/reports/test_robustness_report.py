from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.quant.reports.robustness_report import classify_robustness, market_state_decomposition, write_robustness_report


def test_classify_robustness_uses_thresholds() -> None:
    robust = classify_robustness({"sharpe": 0.8, "max_drawdown": -0.1})
    weak = classify_robustness({"sharpe": 0.1, "max_drawdown": -0.5})

    assert robust["label"] == "robust"
    assert weak["label"] == "not_robust"


def test_write_robustness_report_outputs_label_and_optional_tables(tmp_path: Path) -> None:
    artifacts = write_robustness_report(
        tmp_path,
        {"sharpe": 0.8, "max_drawdown": -0.1},
        yearly_summary=pd.DataFrame([{"market": "us", "year": 2024, "period": 20, "rank_ic_mean": 0.03}]),
    )

    payload = json.loads((tmp_path / "robustness_report.json").read_text(encoding="utf-8"))
    assert payload["label"] == "robust"
    assert Path(artifacts["yearly_factor_summary"]).exists()
    assert "label" in (tmp_path / "robustness_report.md").read_text(encoding="utf-8")


def test_market_state_decomposition_outputs_regime_rows() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-01", periods=40).date.astype(str),
            "portfolio_value": [100 + i for i in range(40)],
            "daily_return": [0.0] + [0.01] * 39,
            "benchmark_value": [100 + i for i in range(40)],
            "benchmark_return": [0.0] + [0.01] * 39,
            "turnover": [0.0] * 40,
            "market": ["us"] * 40,
        }
    )

    result = market_state_decomposition(frame)

    assert not result.empty
    assert {"market_state", "sharpe", "max_drawdown"}.issubset(result.columns)
