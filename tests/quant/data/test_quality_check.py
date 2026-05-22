from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.quant.data.providers.fixture_provider import FixtureDataProvider
from src.quant.data.quality_check import dataframe_hash, run_quality_checks

FIXTURE_DIR = Path("tests/fixtures/quant")


def _tables():
    provider = FixtureDataProvider(FIXTURE_DIR)
    return provider.get_daily_bar(), provider.get_daily_basic(), provider.get_calendar(), provider.get_universe()


def test_quality_check_passes_sample_fixture() -> None:
    daily_bar, daily_basic, calendar, universe = _tables()

    report = run_quality_checks(daily_bar, daily_basic, calendar, universe, fixture_dir=FIXTURE_DIR)

    assert report.passed
    assert report.stats["universe_size"] == 60
    assert report.stats["daily_bar_rows"] == 46_920
    assert report.stats["start_date"] == "2022-01-03"
    assert report.stats["end_date"] == "2024-12-31"
    assert report.stats["daily_bar_hash"] == dataframe_hash(daily_bar)
    assert "PASS" in report.to_text()


def test_quality_check_detects_ohlc_and_volume_errors() -> None:
    daily_bar, daily_basic, calendar, universe = _tables()
    broken = daily_bar.head(20).copy()
    broken.loc[broken.index[0], "high"] = broken.loc[broken.index[0], "low"] - 0.01
    broken.loc[broken.index[1], "volume"] = -1

    report = run_quality_checks(broken, daily_basic.head(20), calendar, universe, fixture_dir=None)

    checks = {issue.check for issue in report.issues}
    assert not report.passed
    assert "ohlc_legal" in checks
    assert "daily_bar_non_negative" in checks


def test_quality_check_detects_non_open_dates_and_missing_runs() -> None:
    daily_bar, daily_basic, calendar, universe = _tables()
    symbol = daily_bar["symbol"].iloc[0]
    broken = daily_bar[~((daily_bar["symbol"] == symbol) & (daily_bar["date"].between("2022-01-03", "2022-01-12")))].copy()
    weekend_row = daily_bar.iloc[[0]].copy()
    weekend_row.loc[:, "date"] = "2022-01-01"
    broken = pd.concat([broken, weekend_row], ignore_index=True)

    report = run_quality_checks(broken, daily_basic, calendar, universe, fixture_dir=None, max_consecutive_missing_days=5)

    checks = {issue.check for issue in report.issues}
    assert not report.passed
    assert "date_trade_calendar" in checks
    assert "consecutive_missing_days" in checks


def test_quality_check_flags_universe_size_outside_sample_bounds() -> None:
    daily_bar, daily_basic, calendar, universe = _tables()
    small_universe = universe.head(10).copy()

    report = run_quality_checks(daily_bar, daily_basic, calendar, small_universe, fixture_dir=None)

    assert not report.passed
    assert any(issue.check == "universe_size" for issue in report.issues)
