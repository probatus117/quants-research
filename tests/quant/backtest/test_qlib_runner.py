from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import src.quant.data.qlib_converter as qlib_converter
import src.quant.backtest.qlib_runner as qlib_runner
from src.quant.backtest.cost_model import CostConfig
from src.quant.backtest.pandas_runner import BacktestConfig
from src.quant.backtest.qlib_runner import run_qlib_backtest, write_qlib_vs_pandas_comparison
from src.quant.data.qlib_converter import convert_parquet_to_qlib
from src.quant.data.storage import write_parquet


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2024-01-02", "market": "cn", "symbol": "AAA", "adj_close": 100.0, "is_suspended": False},
            {"date": "2024-01-03", "market": "cn", "symbol": "AAA", "adj_close": 101.0, "is_suspended": False},
            {"date": "2024-02-01", "market": "cn", "symbol": "AAA", "adj_close": 102.0, "is_suspended": False},
        ]
    )


def _signal() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2024-01-02", "market": "cn", "symbol": "AAA", "score": 1.0},
            {"date": "2024-01-03", "market": "cn", "symbol": "AAA", "score": 1.0},
            {"date": "2024-02-01", "market": "cn", "symbol": "AAA", "score": 1.0},
        ]
    )


def test_qlib_converter_writes_skip_reason_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qlib_converter, "HAS_QLIB", False)
    monkeypatch.setattr(qlib_converter, "qlib", None)

    result = convert_parquet_to_qlib(parquet_root=tmp_path / "parquet", output_dir=tmp_path / "qlib")

    summary = json.loads((tmp_path / "qlib" / "qlib_conversion_summary.json").read_text(encoding="utf-8"))
    assert result.fallback_used is True
    assert "pyqlib is not installed" in str(result.skip_reason)
    assert summary["skip_reason"] == result.skip_reason


def test_qlib_converter_writes_staging_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_parquet(_bars(), "daily_bar", root=tmp_path / "parquet")
    monkeypatch.setattr(qlib_converter, "HAS_QLIB", True)
    monkeypatch.setattr(qlib_converter, "qlib", object())

    result = convert_parquet_to_qlib(parquet_root=tmp_path / "parquet", output_dir=tmp_path / "qlib", market="cn")

    assert result.available is True
    assert (tmp_path / "qlib" / "cn" / "csv_staging" / "daily_bar.csv").exists()
    assert (tmp_path / "qlib" / "cn" / "instruments.txt").read_text(encoding="utf-8").strip() == "AAA"


def test_qlib_runner_writes_skip_reason_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qlib_runner, "check_qlib_capability", lambda: qlib_converter.QlibCapability(False, "missing qlib"))

    result = run_qlib_backtest(_signal(), _bars(), output_dir=tmp_path)

    assert result.fallback_used is True
    assert result.skip_reason == "missing qlib"
    assert (tmp_path / "qlib_run_summary.json").exists()


def test_qlib_runner_available_path_outputs_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qlib_runner, "check_qlib_capability", lambda: qlib_converter.QlibCapability(True))

    result = run_qlib_backtest(
        _signal(),
        _bars(),
        BacktestConfig(top_n=1, market="cn", cost=CostConfig(buy_cost=0, sell_cost=0, min_cost=0)),
        output_dir=tmp_path,
    )

    assert result.available is True
    assert (tmp_path / "portfolio_value.csv").exists()
    assert "sharpe" in result.metrics


def test_write_qlib_vs_pandas_comparison(tmp_path: Path) -> None:
    path = write_qlib_vs_pandas_comparison(
        {"annual_return": 0.11, "sharpe": 1.2, "max_drawdown": -0.1},
        {"annual_return": 0.10, "sharpe": 1.0, "max_drawdown": -0.2},
        output_path=tmp_path / "comparison.md",
    )

    text = path.read_text(encoding="utf-8")
    assert "Qlib vs Pandas" in text
    assert "annual_return" in text
