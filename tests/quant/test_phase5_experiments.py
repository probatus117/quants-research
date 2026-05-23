from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from src.quant.experiments.config_hash import calculate_config_hash, short_config_hash
from src.quant.experiments.registry import (
    EXPERIMENT_ID_PATTERN,
    create_experiment,
    get_experiment,
    list_experiments,
    save_artifact,
    update_status,
)
from src.quant.reports.markdown_report import (
    SECTION_TITLES,
    generate_compare_report,
    generate_experiment_report,
    sync_report_summary_to_neo4j,
    write_report_summary,
)
from tools.quant_experiment import main as quant_experiment_main
from tools.quant_report import main as quant_report_main


def _config() -> dict[str, object]:
    return {
        "backtest": {
            "signal": "composite_v1",
            "universe": "sample_a",
            "frequency": "monthly",
            "top_n": 10,
            "weight": "equal",
        }
    }


def _data_version() -> dict[str, object]:
    return {
        "data_version": "fixture-v1",
        "universe": "sample_a",
        "start_date": "2022-01-01",
        "end_date": "2024-12-31",
    }


def _metrics() -> dict[str, float]:
    return {
        "annual_return": 0.123456,
        "sharpe": 1.25,
        "max_drawdown": -0.08,
        "turnover": 2.5,
    }


def test_config_hash_is_deterministic_for_same_inputs() -> None:
    first = calculate_config_hash(_config(), _data_version())
    reordered_config = {"backtest": dict(reversed(list(_config()["backtest"].items())))}  # type: ignore[index, union-attr]
    second = calculate_config_hash(reordered_config, dict(reversed(list(_data_version().items()))))

    assert first == second
    assert short_config_hash(_config(), _data_version()) == first[:10]


def test_registry_creates_required_structure_and_unique_ids(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    now = datetime(2026, 5, 23, 9, 30, 0)
    first = create_experiment(_config(), _data_version(), "cn", "backtest", root=root, now=now)
    second = create_experiment(_config(), _data_version(), "cn", "backtest", root=root, now=now)

    assert EXPERIMENT_ID_PATTERN.match(first["experiment_id"])
    assert first["experiment_id"] != second["experiment_id"]
    assert first["experiment_id"].startswith("EXP_20260523_093000_cn_backtest_")
    assert second["experiment_id"].startswith("EXP_20260523_093001_cn_backtest_")

    experiment_dir = root / first["experiment_id"]
    assert (experiment_dir / "config.yaml").exists()
    assert (experiment_dir / "data_version.json").exists()
    assert (experiment_dir / "metrics.json").exists()
    assert (experiment_dir / "charts").is_dir()
    assert (experiment_dir / "report.md").exists()
    assert get_experiment(first["experiment_id"], root)["status"] == "running"
    assert [item["experiment_id"] for item in list_experiments(root)] == [
        second["experiment_id"],
        first["experiment_id"],
    ]


def test_registry_saves_artifacts_and_validates_status_flow(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    record = create_experiment(_config(), _data_version(), "cn", "backtest", root=root)
    experiment_id = record["experiment_id"]
    metrics_path = save_artifact(experiment_id, "metrics.json", _metrics(), root=root)

    assert json.loads(metrics_path.read_text(encoding="utf-8"))["sharpe"] == 1.25
    assert update_status(experiment_id, "success", root=root)["status"] == "success"
    assert update_status(experiment_id, "success", root=root)["status"] == "success"
    with pytest.raises(ValueError, match="terminal experiment"):
        update_status(experiment_id, "failed", root=root)


def test_markdown_report_uses_metrics_artifact_and_writes_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "experiments"
    history_dir = tmp_path / "history" / "quant"
    record = create_experiment(_config(), _data_version(), "cn", "backtest", root=root)
    experiment_id = record["experiment_id"]
    save_artifact(experiment_id, "metrics.json", _metrics(), root=root)
    update_status(experiment_id, "success", root=root)

    report_path = generate_experiment_report(experiment_id, "backtest_report", root)
    report = report_path.read_text(encoding="utf-8")

    for title in SECTION_TITLES:
        assert f"## {title}" in report
    assert "| `annual_return` | 0.123456 |" in report
    assert "| `sharpe` | 1.25 |" in report
    assert "This report provides traceable quant evidence, not buy/sell advice." in report

    summary_path = write_report_summary(experiment_id, "backtest_report", report_path, root, history_dir)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["category"] == "quant"
    assert summary["metrics"]["max_drawdown"] == -0.08

    monkeypatch.setenv("NEO4J_MODE", "off")
    assert sync_report_summary_to_neo4j(summary_path) == {"status": "skipped", "reason": "NEO4J_MODE=off"}


def test_compare_report_and_clis(tmp_path: Path) -> None:
    root = tmp_path / "experiments"
    history_dir = tmp_path / "history" / "quant"
    first = create_experiment(_config(), _data_version(), "cn", "backtest", root=root)
    second = create_experiment(
        {"backtest": {**_config()["backtest"], "top_n": 20}},  # type: ignore[index]
        _data_version(),
        "cn",
        "backtest",
        root=root,
    )
    for record, sharpe in [(first, 1.25), (second, 0.75)]:
        save_artifact(record["experiment_id"], "metrics.json", {**_metrics(), "sharpe": sharpe}, root=root)
        update_status(record["experiment_id"], "success", root=root)

    compare_path = generate_compare_report(
        [first["experiment_id"], second["experiment_id"]],
        experiments_root=root,
        output_path=tmp_path / "compare.md",
    )
    compare = compare_path.read_text(encoding="utf-8")
    assert first["experiment_id"] in compare
    assert second["experiment_id"] in compare
    assert re.search(r"\|\s*`?sharpe`?\s*\|", compare) or "sharpe" in compare

    assert quant_report_main(
        [
            "generate",
            "--experiment-id",
            first["experiment_id"],
            "--report-type",
            "backtest_report",
            "--experiments-root",
            str(root),
            "--history-dir",
            str(history_dir),
        ]
    ) == 0
    assert quant_experiment_main(["list", "--experiments-root", str(root), "--limit", "2"]) == 0
    assert quant_experiment_main(
        [
            "compare",
            first["experiment_id"],
            second["experiment_id"],
            "--experiments-root",
            str(root),
            "--output",
            str(tmp_path / "cli_compare.md"),
        ]
    ) == 0
    assert (tmp_path / "cli_compare.md").exists()
