from __future__ import annotations

from pathlib import Path

import pytest

from src.quant.data.providers.fixture_provider import FixtureDataError, FixtureDataProvider

FIXTURE_DIR = Path("tests/fixtures/quant")


def test_fixture_provider_returns_standard_tables() -> None:
    provider = FixtureDataProvider(FIXTURE_DIR)

    daily_bar = provider.get_daily_bar()
    daily_basic = provider.get_daily_basic()
    calendar = provider.get_calendar()
    universe = provider.get_universe()

    assert len(universe) == 60
    assert len(daily_bar) == 46_920
    assert len(daily_basic) == 46_920
    assert len(calendar) == 1_096
    assert daily_bar["date"].min() == "2022-01-03"
    assert daily_bar["date"].max() == "2024-12-31"
    assert daily_bar["symbol"].str.len().eq(6).all()
    assert set(universe["market_cap_bucket"]) == {"large", "mid", "small"}
    assert universe["industry"].nunique() == 10


def test_fixture_provider_filters_date_and_symbols() -> None:
    provider = FixtureDataProvider(FIXTURE_DIR)

    df = provider.get_daily_bar(start_date="2022-01-03", end_date="2022-01-04", symbols=["2", "600001"])

    assert sorted(df["date"].unique().tolist()) == ["2022-01-03", "2022-01-04"]
    assert sorted(df["symbol"].unique().tolist()) == ["000002", "600001"]
    assert len(df) == 4


def test_fixture_provider_verifies_hash_manifest() -> None:
    provider = FixtureDataProvider(FIXTURE_DIR)

    hashes = provider.verify_fixture_hashes()

    assert hashes["sample_daily_bar.csv"] == "244901f78f943cc5925fe14543c1890cdba378185d4b0647bb9dca4abb4b875c"
    assert hashes["sample_daily_basic.csv"] == "477a299e1185e4f8a667e5e31167b59239aba88209e1e82d984bbac6226269ad"


def test_fixture_provider_rejects_hash_mismatch(tmp_path: Path) -> None:
    for path in FIXTURE_DIR.glob("sample_*.csv"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "sample_hashes.json").write_text('{"sample_daily_bar.csv": "bad"}\n', encoding="utf-8")

    with pytest.raises(FixtureDataError, match="Fixture hash mismatch"):
        FixtureDataProvider(tmp_path)
