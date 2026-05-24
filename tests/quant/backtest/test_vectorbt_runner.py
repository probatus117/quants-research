from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import src.quant.backtest.vectorbt_runner as vectorbt_runner
from src.quant.backtest.vectorbt_runner import run_vectorbt_grid


def _bars() -> pd.DataFrame:
    rows = []
    for idx, date in enumerate(pd.bdate_range("2024-01-01", periods=80)):
        rows.append({"date": date.date().isoformat(), "market": "us", "symbol": "ETF", "adj_close": 100 + idx})
    return pd.DataFrame(rows)


def test_vectorbt_grid_writes_skip_reason_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vectorbt_runner, "HAS_VECTORBT", False)
    monkeypatch.setattr(vectorbt_runner, "vbt", None)

    result = run_vectorbt_grid(_bars(), output_dir=tmp_path)

    summary = json.loads((tmp_path / "vectorbt_summary.json").read_text(encoding="utf-8"))
    assert result.fallback_used is True
    assert "vectorbt is not installed" in str(result.skip_reason)
    assert summary["skip_reason"] == result.skip_reason


def test_vectorbt_grid_uses_mocked_portfolio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePortfolio:
        def total_return(self):
            return pd.Series([0.12])

        def sharpe_ratio(self):
            return pd.Series([1.4])

    class FakePortfolioFactory:
        @staticmethod
        def from_signals(close, entries, exits, init_cash, fees):
            return FakePortfolio()

    class FakeVectorbt:
        Portfolio = FakePortfolioFactory

    monkeypatch.setattr(vectorbt_runner, "HAS_VECTORBT", True)
    monkeypatch.setattr(vectorbt_runner, "vbt", FakeVectorbt())

    result = run_vectorbt_grid(_bars(), fast_windows=(5,), slow_windows=(20,), output_dir=tmp_path)

    assert result.available is True
    assert result.ranking.iloc[0]["sharpe"] == 1.4
    assert (tmp_path / "ranking.csv").exists()
    assert (tmp_path / "heatmap.png").exists()
