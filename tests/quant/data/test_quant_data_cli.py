from __future__ import annotations

import json
from pathlib import Path

from src.quant.data.storage import read_parquet
from tools.quant_data import main

FIXTURE_DIR = Path("tests/fixtures/quant")


def test_quant_data_check_cli_outputs_pass(capsys) -> None:
    exit_code = main(["check", "--source", "fixture", "--fixture-dir", str(FIXTURE_DIR)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Quant data quality report: PASS" in captured.out


def test_quant_data_update_cli_writes_parquet_and_data_version(tmp_path: Path) -> None:
    exit_code = main([
        "update",
        "--source",
        "fixture",
        "--fixture-dir",
        str(FIXTURE_DIR),
        "--output-dir",
        str(tmp_path),
    ])

    assert exit_code == 0
    daily_bar = read_parquet("daily_bar", root=tmp_path / "parquet")
    data_version = json.loads((tmp_path / "data_version.json").read_text(encoding="utf-8"))
    assert len(daily_bar) == 46_920
    assert data_version["source"] == "fixture"
    assert data_version["start_date"] == "2022-01-03"
    assert data_version["end_date"] == "2024-12-31"
    assert data_version["row_count"]["daily_bar"] == 46_920
