from __future__ import annotations

import json
from pathlib import Path

from src.quant.evaluation.exporter import export_evaluation
from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation
from src.quant.reports.factor_report import render_factor_report, write_factor_report
from tools.quant_eval import main as quant_eval_main


def test_factor_report_renders_required_sections(prepared_quant_tables: dict[str, object], tmp_path: Path) -> None:
    result = run_minimal_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1", min_coverage=0.99),
    )
    report = render_factor_report(result.factor_summary, result.coverage)

    assert "# Factor Evaluation Report: momentum_12_1" in report
    assert "## IC / Rank IC" in report
    assert "## 分组收益" in report
    assert "覆盖率存在不足" in report

    output_path = write_factor_report(result.factor_summary, result.coverage, tmp_path / "report.md")
    assert output_path.exists()


def test_exporter_and_cli_write_evaluation_artifacts(prepared_quant_tables: dict[str, object], tmp_path: Path) -> None:
    result = run_minimal_evaluation(
        prepared_quant_tables["factor_value"],
        prepared_quant_tables["daily_bar"],
        MinimalEvaluationConfig(factor_name="momentum_12_1"),
    )
    paths = export_evaluation(result, tmp_path / "manual")
    assert paths["factor_summary"].exists()
    assert paths["ic_timeseries"].exists()
    assert paths["quantile_returns"].exists()
    assert paths["coverage"].exists()
    assert json.loads(paths["coverage"].read_text(encoding="utf-8"))["summary"]["dates"] > 0

    assert quant_eval_main([
        "run",
        "--input-dir",
        str(prepared_quant_tables["root"]),
        "--output-dir",
        str(tmp_path / "cli"),
        "--factor",
        "momentum_12_1",
    ]) == 0
    assert (tmp_path / "cli" / "momentum_12_1" / "report.md").exists()
