from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import src.quant.evaluation.alphalens_runner as alphalens_runner
from src.quant.evaluation.alphalens_runner import run_alphalens_evaluation
from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig
from tools.quant_eval import run_evaluation


def test_alphalens_runner_writes_skip_reason_when_missing(
    prepared_quant_tables: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alphalens_runner, "HAS_ALPHALENS", False)
    monkeypatch.setattr(alphalens_runner, "al", None)

    result = run_alphalens_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1", periods=(5, 20, 60)),
        output_dir=tmp_path,
    )

    summary = json.loads((tmp_path / "alphalens_summary.json").read_text(encoding="utf-8"))
    assert result.fallback_used is True
    assert "alphalens-reloaded is not installed" in str(result.skip_reason)
    assert summary["skip_reason"] == result.skip_reason
    assert (tmp_path / "minimal_report.md").exists()


def test_alphalens_runner_can_use_mocked_tear_sheet(
    prepared_quant_tables: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeUtils:
        @staticmethod
        def get_clean_factor_and_forward_returns(factor, prices, periods, quantiles, max_loss):
            frame = factor.rename("factor").to_frame()
            for period in periods:
                frame[f"{period}D"] = frame["factor"] * 0.01
            frame["factor_quantile"] = 1
            return frame

    class FakeTears:
        @staticmethod
        def create_full_tear_sheet(factor_data):
            import matplotlib.pyplot as plt

            plt.figure()
            plt.plot([0, 1], [0, 1])

    class FakeAlphalens:
        utils = FakeUtils()
        tears = FakeTears()

    monkeypatch.setattr(alphalens_runner, "HAS_ALPHALENS", True)
    monkeypatch.setattr(alphalens_runner, "al", FakeAlphalens())

    result = run_alphalens_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1", periods=(5,)),
        output_dir=tmp_path,
    )

    assert result.available is True
    assert result.fallback_used is False
    assert (tmp_path / "tear_sheet.html").exists()
    assert (tmp_path / "ic.png").exists()
    assert (tmp_path / "quantile_returns.png").exists()


def test_quant_eval_cli_includes_alphalens_skip_metadata(
    prepared_quant_tables: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alphalens_runner, "HAS_ALPHALENS", False)
    monkeypatch.setattr(alphalens_runner, "al", None)

    payload = run_evaluation(
        input_dir=prepared_quant_tables["root"],
        output_dir=tmp_path,
        factor="momentum_12_1",
        periods="5,20,60",
        use_alphalens=True,
    )

    assert payload["alphalens"]["fallback_used"] is True
    assert "skip_reason" in payload["alphalens"]


@pytest.mark.skipif(not alphalens_runner.HAS_ALPHALENS, reason="alphalens-reloaded is not installed")
def test_alphalens_ic_summary_matches_minimal_runner_on_fixture(
    prepared_quant_tables: dict[str, object],
    tmp_path: Path,
) -> None:
    result = run_alphalens_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1", periods=(5, 20, 60)),
        output_dir=tmp_path,
    )

    assert result.ic_comparison["max_abs_ic_mean_diff"] is not None
    assert result.ic_comparison["max_abs_ic_mean_diff"] < 0.01
    assert result.ic_comparison["max_abs_rank_ic_mean_diff"] < 0.01
