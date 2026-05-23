from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.quant.data.storage import read_parquet
from tools.quant_data import main as quant_data_main
from tools.quant_factor import main as quant_factor_main

FIXTURE_DIR = Path("tests/fixtures/quant")


def test_quant_factor_compute_cli_writes_factor_store_and_coverage(tmp_path: Path) -> None:
    assert quant_data_main([
        "update",
        "--source",
        "fixture",
        "--fixture-dir",
        str(FIXTURE_DIR),
        "--output-dir",
        str(tmp_path),
    ]) == 0

    exit_code = quant_factor_main([
        "compute",
        "--input-dir",
        str(tmp_path),
        "--output-dir",
        str(tmp_path),
        "--factors",
        "all",
        "--no-charts",
    ])

    assert exit_code == 0
    factor_values = read_parquet("factor_value", root=tmp_path / "parquet")
    coverage = json.loads((tmp_path / "factors" / "coverage.json").read_text(encoding="utf-8"))

    assert set(factor_values["factor_name"].unique()) == {"value_bp", "momentum_12_1", "lowvol_60d"}
    assert set(
        [
            "date",
            "market",
            "symbol",
            "factor_name",
            "raw_value",
            "winsorized_value",
            "zscore",
            "percentile",
            "direction",
            "universe",
        ]
    ).issubset(factor_values.columns)
    assert len(factor_values) == 46_920 * 3

    first_date = str(factor_values["date"].min())
    latest_date = str(factor_values["date"].max())
    by_key = {(row["factor_name"], row["market"], row["date"]): row for row in coverage["by_date"]}
    assert by_key[("value_bp", "cn", first_date)]["valid_count"] == by_key[("value_bp", "cn", first_date)]["universe_total"]
    assert by_key[("momentum_12_1", "cn", first_date)]["valid_count"] == 0
    assert by_key[("lowvol_60d", "cn", first_date)]["valid_count"] == 0
    assert by_key[("momentum_12_1", "cn", latest_date)]["coverage"] == 1.0
    assert by_key[("lowvol_60d", "cn", latest_date)]["coverage"] == 1.0

    for (_, _, date), group in factor_values.dropna(subset=["zscore"]).groupby(["factor_name", "market", "date"]):
        if len(group) > 1:
            assert np.isclose(group["zscore"].mean(), 0.0)
            assert np.isclose(group["zscore"].std(), 1.0)
            assert group["percentile"].between(0, 1).all()
            break


def test_quant_factor_compute_is_deterministic(tmp_path: Path) -> None:
    quant_data_main([
        "update",
        "--source",
        "fixture",
        "--fixture-dir",
        str(FIXTURE_DIR),
        "--output-dir",
        str(tmp_path),
    ])

    args = [
        "compute",
        "--input-dir",
        str(tmp_path),
        "--output-dir",
        str(tmp_path),
        "--factors",
        "value_bp",
        "--no-charts",
    ]
    assert quant_factor_main(args) == 0
    first = read_parquet("factor_value", root=tmp_path / "parquet")
    assert quant_factor_main(args) == 0
    second = read_parquet("factor_value", root=tmp_path / "parquet")

    assert first.equals(second)
