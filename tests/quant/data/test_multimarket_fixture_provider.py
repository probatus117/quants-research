from __future__ import annotations

from pathlib import Path

from src.quant.data.providers.fixture_provider import FixtureDataProvider
from tools.quant_data import main as quant_data_main


FIXTURE_DIR = Path("tests/fixtures/quant")


def test_fixture_provider_loads_three_markets() -> None:
    provider = FixtureDataProvider(FIXTURE_DIR)
    for market, currency in [("cn", "CNY"), ("us", "USD"), ("jp", "JPY")]:
        universe = provider.get_universe(market=market)
        bars = provider.get_daily_bar(market=market, symbols=universe["symbol"].head(2).tolist())
        benchmark = provider.get_benchmark_return(market, "equal_weight")

        assert universe["market"].eq(market).all()
        assert universe["currency"].eq(currency).all()
        assert universe["symbol"].nunique() == 60
        assert bars["market"].eq(market).all()
        assert benchmark["benchmark_return"].notna().all()


def test_quant_data_check_all_markets() -> None:
    assert quant_data_main(["check", "--fixture-dir", str(FIXTURE_DIR), "--market", "all", "--json"]) == 0
