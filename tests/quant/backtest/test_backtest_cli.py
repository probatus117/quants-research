from __future__ import annotations

import json
from pathlib import Path

from src.quant.data.storage import read_parquet
from tools.quant_backtest import main as quant_backtest_main
from tools.quant_data import main as quant_data_main
from tools.quant_factor import main as quant_factor_main

FIXTURE_DIR = Path("tests/fixtures/quant")


def _prepare_quant_data(tmp_path: Path) -> None:
    assert quant_data_main(
        [
            "update",
            "--source",
            "fixture",
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    assert quant_factor_main(
        [
            "compute",
            "--input-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path),
            "--factors",
            "all",
            "--no-charts",
        ]
    ) == 0


def test_quant_backtest_cli_outputs_artifacts_for_composite_and_single_factor(tmp_path: Path) -> None:
    _prepare_quant_data(tmp_path)
    output_dir = tmp_path / "backtest"

    assert quant_backtest_main(
        [
            "run",
            "--input-dir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--signal",
            "composite_v1",
            "--top-n",
            "10",
            "--no-charts",
        ]
    ) == 0
    assert quant_backtest_main(
        [
            "run",
            "--input-dir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--signal",
            "momentum_12_1",
            "--top-n",
            "10",
            "--no-charts",
        ]
    ) == 0

    composite_dir = output_dir / "composite_v1"
    metrics = json.loads((composite_dir / "metrics.json").read_text(encoding="utf-8"))
    signal = read_parquet("signal", root=composite_dir / "parquet")

    assert (composite_dir / "portfolio_value.csv").exists()
    assert (composite_dir / "positions.csv").exists()
    assert (composite_dir / "trades.csv").exists()
    assert (composite_dir / "report.md").exists()
    assert {"annual_return", "annual_volatility", "sharpe", "max_drawdown", "calmar"}.issubset(metrics)
    assert {"turnover", "excess_return", "benchmark_return"}.issubset(metrics)
    assert signal["signal_name"].unique().tolist() == ["composite_v1"]
    assert (output_dir / "momentum_12_1" / "metrics.json").exists()


def test_quant_backtest_cli_is_deterministic(tmp_path: Path) -> None:
    _prepare_quant_data(tmp_path)
    args = [
        "run",
        "--input-dir",
        str(tmp_path),
        "--output-dir",
        str(tmp_path / "backtest"),
        "--signal",
        "composite_v1",
        "--top-n",
        "10",
        "--no-charts",
    ]

    assert quant_backtest_main(args) == 0
    first = (tmp_path / "backtest" / "composite_v1" / "portfolio_value.csv").read_text(encoding="utf-8")
    assert quant_backtest_main(args) == 0
    second = (tmp_path / "backtest" / "composite_v1" / "portfolio_value.csv").read_text(encoding="utf-8")

    assert first == second
