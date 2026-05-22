from __future__ import annotations

import pandas as pd
import pytest

from src.quant.data.storage import read_parquet
from src.quant.factors.base import BaseFactor, FactorConfig, FactorError, FactorResult


class DummyFactor(BaseFactor):
    factor_name = "dummy"
    required_columns = ("date", "symbol", "value")

    def compute(self, df: pd.DataFrame) -> FactorResult:
        data = self.validate_input(df).copy()
        data["raw_value"] = data["value"] * 2
        return self.build_result(data)


def test_base_factor_builds_standard_result() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "symbol": ["000001", "000002"],
            "value": [1.5, 2.0],
        }
    )

    result = DummyFactor(FactorConfig(name="dummy", universe="sample")).compute(df)

    assert list(result.values.columns) == [
        "date",
        "symbol",
        "factor_name",
        "raw_value",
        "direction",
        "universe",
    ]
    assert result.values["raw_value"].tolist() == [3.0, 4.0]
    assert result.values["factor_name"].unique().tolist() == ["dummy"]
    assert result.values["universe"].unique().tolist() == ["sample"]


def test_base_factor_rejects_missing_columns() -> None:
    with pytest.raises(FactorError, match="missing required columns"):
        DummyFactor().compute(pd.DataFrame({"date": ["2024-01-02"], "symbol": ["000001"]}))


def test_base_factor_rejects_mismatched_config_name() -> None:
    with pytest.raises(FactorError, match="does not match"):
        DummyFactor(FactorConfig(name="wrong"))


def test_base_factor_save_round_trips(tmp_path) -> None:
    df = pd.DataFrame({"date": ["2024-01-02"], "symbol": ["000001"], "value": [2.0]})
    factor = DummyFactor()
    result = factor.compute(df)

    output = factor.save(result, root=tmp_path)
    loaded = read_parquet("factor_value", root=tmp_path)

    assert output == tmp_path / "factor_value" / "data.parquet"
    pd.testing.assert_frame_equal(loaded, result.values)
