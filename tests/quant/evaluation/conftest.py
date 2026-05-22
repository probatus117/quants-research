from __future__ import annotations

from pathlib import Path

import pytest

from src.quant.data.storage import read_parquet
from tools.quant_data import main as quant_data_main
from tools.quant_factor import main as quant_factor_main


FIXTURE_DIR = Path("tests/fixtures/quant")


@pytest.fixture()
def prepared_quant_tables(tmp_path: Path) -> dict[str, object]:
    assert quant_data_main([
        "update",
        "--source",
        "fixture",
        "--fixture-dir",
        str(FIXTURE_DIR),
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert quant_factor_main([
        "compute",
        "--input-dir",
        str(tmp_path),
        "--output-dir",
        str(tmp_path),
        "--factors",
        "all",
        "--no-charts",
    ]) == 0
    return {
        "root": tmp_path,
        "daily_bar": read_parquet("daily_bar", root=tmp_path / "parquet"),
        "factor_value": read_parquet("factor_value", root=tmp_path / "parquet"),
    }
