from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.evaluation.ic_analysis import calculate_ic_timeseries, summarize_ic
from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation


def test_ic_summary_calculates_pearson_and_rank_ic() -> None:
    evaluation_input = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 4 + ["2024-01-02"] * 4,
            "zscore": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
            "forward_return_5d": [0.01, 0.02, 0.03, 0.04, 0.04, 0.03, 0.02, 0.01],
        }
    )

    timeseries = calculate_ic_timeseries(evaluation_input, periods=(5,))
    summary = summarize_ic(timeseries)

    assert np.isclose(timeseries.loc[0, "ic"], 1.0)
    assert np.isclose(timeseries.loc[1, "ic"], -1.0)
    assert np.isclose(summary.loc[0, "ic_mean"], 0.0)
    assert np.isclose(summary.loc[0, "rank_ic_mean"], 0.0)
    assert np.isclose(summary.loc[0, "ic_positive_ratio"], 0.5)


def test_minimal_runner_produces_multi_period_ic_series(prepared_quant_tables: dict[str, object]) -> None:
    result = run_minimal_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1"),
    )

    assert set(result.ic_timeseries["period"].unique()) == {5, 20, 60}
    assert set(result.ic_summary["period"]) == {5, 20, 60}
    assert result.ic_timeseries["ic"].notna().any()
    assert result.ic_timeseries["rank_ic"].notna().any()
