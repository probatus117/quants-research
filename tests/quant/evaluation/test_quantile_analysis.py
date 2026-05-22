from __future__ import annotations

import numpy as np
import pandas as pd

from src.quant.evaluation.quantile_analysis import calculate_quantile_returns, summarize_quantile_returns


def test_quantile_returns_calculates_five_groups_and_long_short() -> None:
    evaluation_input = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 10,
            "zscore": list(range(10)),
            "forward_return_5d": [value / 100.0 for value in range(10)],
        }
    )

    returns = calculate_quantile_returns(evaluation_input, periods=(5,), quantiles=5)
    summary = summarize_quantile_returns(returns)

    assert set(returns["quantile"].astype(str)) == {"1", "2", "3", "4", "5", "long_short"}
    q1 = summary[(summary["period"] == 5) & (summary["quantile"] == "1")]["mean_forward_return"].iloc[0]
    q5 = summary[(summary["period"] == 5) & (summary["quantile"] == "5")]["mean_forward_return"].iloc[0]
    spread = summary[(summary["period"] == 5) & (summary["quantile"] == "long_short")][
        "mean_forward_return"
    ].iloc[0]
    assert np.isclose(q1, 0.005)
    assert np.isclose(q5, 0.085)
    assert np.isclose(spread, q5 - q1)


def test_quantile_returns_supports_multi_periods(prepared_quant_tables: dict[str, object]) -> None:
    from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation

    result = run_minimal_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1"),
    )

    assert set(result.quantile_returns["period"].unique()) == {5, 20, 60}
    assert "long_short" in set(result.quantile_returns["quantile"].astype(str))
