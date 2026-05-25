from __future__ import annotations

import json
from pathlib import Path

import tools.quant_qlib as quant_qlib


def test_quant_qlib_help() -> None:
    output = quant_qlib.build_parser().format_help()
    assert "Qlib native quant research CLI" in output


def test_convert_cli_skip_contract(tmp_path: Path, capsys) -> None:
    rc = quant_qlib.main(
        [
            "convert",
            "--market",
            "cn",
            "--parquet-root",
            str(tmp_path / "parquet"),
            "--output-dir",
            str(tmp_path / "qlib_bin"),
            "--disable-qlib",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    summary = tmp_path / "qlib_bin" / "cn" / "qlib_conversion_summary.json"
    assert rc == 0
    assert payload["fallback_used"] is True
    assert summary.exists()


def test_run_cli_skip_contract(tmp_path: Path, capsys) -> None:
    rc = quant_qlib.main(
        [
            "run",
            "--market",
            "cn",
            "--parquet-root",
            str(tmp_path / "parquet"),
            "--qlib-bin-dir",
            str(tmp_path / "qlib_bin"),
            "--output-dir",
            str(tmp_path / "native"),
            "--disable-qlib",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["fallback_used"] is True
    assert (tmp_path / "native" / "cn" / "qlib_native_summary.json").exists()


def test_run_cli_registers_native_artifacts_and_report(tmp_path: Path, capsys) -> None:
    rc = quant_qlib.main(
        [
            "run",
            "--market",
            "cn",
            "--parquet-root",
            str(tmp_path / "parquet"),
            "--qlib-bin-dir",
            str(tmp_path / "qlib_bin"),
            "--output-dir",
            str(tmp_path / "native"),
            "--experiments-root",
            str(tmp_path / "experiments"),
            "--disable-qlib",
            "--register",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    registry = payload["registry"]
    experiment_dir = Path(registry["experiment_dir"])
    metadata = json.loads((experiment_dir / "metadata.json").read_text(encoding="utf-8"))
    report = Path(registry["report"]).read_text(encoding="utf-8")

    assert rc == 0
    assert metadata["task_type"] == "qlib-native"
    assert (experiment_dir / "qlib_native_summary.json").exists()
    assert (experiment_dir / "qlib_conversion_summary.json").exists()
    assert (experiment_dir / "qlib_vs_pandas_same_signal_comparison.md").exists()
    assert (experiment_dir / "qlib_native_research_comparison.md").exists()
    assert "qlib_native.qlib_data_available" in report
    assert "qlib_conversion.price_adjustment_policy" in report
    assert "qlib_compare.same_signal" in report
    assert "qlib_compare.native_research" in report


def test_compare_modes_write_distinct_reports(tmp_path: Path, capsys) -> None:
    assert quant_qlib.main(["compare", "--market", "cn", "--mode", "same-signal", "--output-dir", str(tmp_path)]) == 0
    same_payload = json.loads(capsys.readouterr().out)
    assert quant_qlib.main(["compare", "--market", "cn", "--mode", "native-research", "--output-dir", str(tmp_path)]) == 0
    native_payload = json.loads(capsys.readouterr().out)

    same_text = Path(same_payload["report"]).read_text(encoding="utf-8")
    native_text = Path(native_payload["report"]).read_text(encoding="utf-8")
    assert "engine-difference audit" in same_text
    assert "descriptive only" in native_text
