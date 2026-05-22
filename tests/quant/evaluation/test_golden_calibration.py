from __future__ import annotations

import json
from pathlib import Path

from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation


GOLDEN_PATH = Path("tests/fixtures/quant/expected_ic_summary.json")


def test_minimal_runner_matches_golden_ic_and_quantile_returns(
    prepared_quant_tables: dict[str, object],
) -> None:
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = run_minimal_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name=expected["factor_name"], periods=tuple(expected["periods"])),
    )
    tolerance = float(expected["tolerance"])

    actual_ic = {str(row["period"]): row for row in result.ic_summary.to_dict(orient="records")}
    for period, expected_row in expected["ic_summary"].items():
        assert abs(actual_ic[period]["ic_mean"] - expected_row["ic_mean"]) < tolerance
        assert abs(actual_ic[period]["rank_ic_mean"] - expected_row["rank_ic_mean"]) < tolerance

    actual_quantile = {
        (str(row["period"]), str(row["quantile"])): row
        for row in result.quantile_summary.to_dict(orient="records")
    }
    for period, expected_quantiles in expected["quantile_returns"].items():
        for quantile, expected_mean in expected_quantiles.items():
            actual_mean = actual_quantile[(period, quantile)]["mean_forward_return"]
            assert abs(actual_mean - expected_mean) < tolerance
