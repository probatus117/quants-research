from __future__ import annotations

import json
from pathlib import Path

from tools.quant_scale_test import main as scale_main


def test_quant_scale_test_duckdb_artifact_has_three_market_counts(tmp_path: Path) -> None:
    output = tmp_path / "scale_report.json"

    assert scale_main(["--sizes", "12", "--duckdb", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["duckdb_rows"][0]["markets"] == ["cn", "us", "jp"]
    if payload["duckdb_rows"][0]["duckdb_available"]:
        assert payload["duckdb_rows"][0]["duckdb_rows"] == payload["duckdb_rows"][0]["pandas_rows"]
