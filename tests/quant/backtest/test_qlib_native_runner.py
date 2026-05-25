from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import src.quant.backtest.qlib_native_runner as qlib_native_runner
from src.quant.backtest.qlib_native_runner import (
    QlibNativeCapability,
    QlibNativeConfig,
    check_qlib_native_capability,
    qlib_portfolio_to_backtest_result,
    qlib_predictions_to_signal,
    run_qlib_native_workflow,
)


def test_native_capability_records_lightgbm_dynamic_library_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(name: str, *args, **kwargs):
        if name == "lightgbm":
            raise OSError("libomp.dylib missing")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    cap = check_qlib_native_capability(require_model=True, require_backtest=False)

    assert cap.qlib_model_available is False
    assert "libomp.dylib" in str(cap.model_skip_reason)


def test_workflow_skip_summary_has_layered_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capability = QlibNativeCapability(
        qlib_data_available=True,
        qlib_model_available=False,
        qlib_backtest_available=True,
        skip_reason="model unavailable",
        model_skip_reason="model unavailable",
    )
    monkeypatch.setattr(qlib_native_runner, "check_qlib_native_capability", lambda require_model=True, require_backtest=True: capability)

    result = run_qlib_native_workflow(QlibNativeConfig(market="cn"), output_dir=tmp_path)

    summary = json.loads((tmp_path / "qlib_native_summary.json").read_text(encoding="utf-8"))
    assert result.fallback_used is True
    assert summary["capability"]["qlib_model_available"] is False
    assert summary["skip_reason"] == "model unavailable"


def test_prediction_bridge_sorts_and_shapes_signal() -> None:
    index = pd.MultiIndex.from_tuples(
        [("2024-01-02", "BBB"), ("2024-01-02", "AAA"), ("2024-01-03", "AAA")],
        names=["datetime", "instrument"],
    )
    prediction = pd.Series([0.1, 0.3, 0.2], index=index)

    signal = qlib_predictions_to_signal(prediction, market="us")

    assert list(signal.columns) == ["date", "market", "symbol", "score"]
    assert signal.iloc[0].to_dict() == {"date": "2024-01-02", "market": "us", "symbol": "AAA", "score": 0.3}


def test_portfolio_bridge_returns_backtest_result() -> None:
    portfolio = pd.DataFrame({"date": ["2024-01-02", "2024-01-03"], "account": [100.0, 101.0]})

    result = qlib_portfolio_to_backtest_result(portfolio, market="jp")

    assert result.portfolio_value["portfolio_value"].tolist() == [100.0, 101.0]
    assert result.portfolio_value["market"].tolist() == ["jp", "jp"]
    assert result.portfolio_value["daily_return"].iloc[1] == pytest.approx(0.01)
