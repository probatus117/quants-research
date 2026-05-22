from __future__ import annotations

import numpy as np

from src.quant.evaluation.input_builder import add_forward_returns, build_evaluation_input


def test_add_forward_returns_matches_shifted_adjusted_prices(prepared_quant_tables: dict[str, object]) -> None:
    daily_bar = prepared_quant_tables["daily_bar"]
    returns = add_forward_returns(daily_bar, periods=(5, 20, 60))
    symbol_rows = returns[returns["symbol"] == "600001"].sort_values("date").reset_index(drop=True)

    expected_5d = symbol_rows.loc[5, "adj_close"] / symbol_rows.loc[0, "adj_close"] - 1.0
    assert np.isclose(symbol_rows.loc[0, "forward_return_5d"], expected_5d)
    assert symbol_rows.tail(5)["forward_return_5d"].isna().all()
    assert symbol_rows.tail(20)["forward_return_20d"].isna().all()
    assert symbol_rows.tail(60)["forward_return_60d"].isna().all()


def test_build_evaluation_input_merges_one_factor_with_forward_returns(
    prepared_quant_tables: dict[str, object],
) -> None:
    evaluation_input = build_evaluation_input(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        "momentum_12_1",
    )

    assert len(evaluation_input) == 46_920
    assert evaluation_input["factor_name"].nunique() == 1
    assert set(["forward_return_5d", "forward_return_20d", "forward_return_60d"]).issubset(
        evaluation_input.columns
    )
    assert evaluation_input["zscore"].notna().any()
    assert evaluation_input["forward_return_60d"].notna().any()
