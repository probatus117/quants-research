"""Offline fixture provider for Phase 1 quant data tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.quant.data.providers.base import QuantDataProvider
from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.data.schema import normalize_symbol, validate_schema


class FixtureDataError(ValueError):
    """Raised when fixture data cannot be loaded or verified."""


class FixtureDataProvider(QuantDataProvider):
    """Read deterministic local CSV fixtures without network access."""

    def __init__(self, fixture_dir: str | Path = "tests/fixtures/quant", verify_hash: bool = True) -> None:
        self.fixture_dir = Path(fixture_dir)
        self.verify_hash = verify_hash
        if not self.fixture_dir.exists():
            raise FixtureDataError(f"Fixture directory not found: {self.fixture_dir}")
        if verify_hash:
            self.verify_fixture_hashes()

    def get_daily_bar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        market = normalize_market(market)
        df = self._read_csv("sample_daily_bar.csv", market=market, bool_columns=["is_suspended"])
        df = self._filter_market(df, market)
        df = self._filter_date_symbol(df, market, start_date, end_date, symbols)
        return validate_schema(df.reset_index(drop=True), "daily_bar")

    def get_daily_basic(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        market = normalize_market(market)
        df = self._read_csv("sample_daily_basic.csv", market=market)
        df = self._filter_market(df, market)
        df = self._filter_date_symbol(df, market, start_date, end_date, symbols)
        return validate_schema(df.reset_index(drop=True), "daily_basic")

    def get_calendar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        market = normalize_market(market)
        df = self._read_csv("sample_calendar.csv", market=market, bool_columns=["is_open"])
        df = self._filter_market(df, market)
        df = self._filter_dates(df, start_date, end_date)
        return validate_schema(df.reset_index(drop=True), "calendar")

    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        market = normalize_market(market)
        df = self._read_csv("sample_universe.csv", market=market, bool_columns=["is_member"])
        df = self._filter_market(df, market)
        df = df[df["universe"] == universe].copy()
        df["symbol"] = df["symbol"].map(lambda value: normalize_symbol(value, market))
        return validate_schema(df.sort_values("symbol").reset_index(drop=True), "dim_security")

    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        """Return fixture index membership using the universe as a deterministic proxy."""
        market = normalize_market(market)
        universe = self.get_universe(market=market)
        output = universe[["market", "symbol", "universe", "is_member"]].copy()
        output["index_code"] = index_code
        return output[["market", "index_code", "symbol", "universe", "is_member"]]

    def get_benchmark_return(
        self,
        market: str,
        index_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return equal-weight fixture benchmark returns for the requested market."""
        bars = self.get_daily_bar(market=market, start_date=start_date, end_date=end_date)
        prices = bars.pivot_table(index="date", columns="symbol", values="adj_close", aggfunc="first").sort_index()
        returns = prices.pct_change().mean(axis=1, skipna=True).fillna(0.0)
        return pd.DataFrame(
            {
                "date": returns.index.astype(str),
                "market": normalize_market(market),
                "index_code": index_code,
                "benchmark_return": returns.to_numpy(),
            }
        )

    def read_all(self, market: str = "cn") -> dict[str, pd.DataFrame]:
        """Return all standard Phase 1 tables keyed by storage table name."""
        universe = self.get_universe(market=market)
        return {
            "daily_bar": self.get_daily_bar(market=market),
            "daily_basic": self.get_daily_basic(market=market),
            "calendar": self.get_calendar(market=market),
            "dim_security": universe,
        }

    def verify_fixture_hashes(self) -> dict[str, str]:
        expected_path = self.fixture_dir / "sample_hashes.json"
        if not expected_path.exists():
            raise FixtureDataError(f"Missing fixture hash manifest: {expected_path}")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        actual = self.fixture_hashes()
        mismatched = {
            name: {"expected": expected_hash, "actual": actual.get(name)}
            for name, expected_hash in expected.items()
            if actual.get(name) != expected_hash
        }
        if mismatched:
            raise FixtureDataError(f"Fixture hash mismatch: {json.dumps(mismatched, sort_keys=True)}")
        return actual

    def fixture_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for path in sorted(self.fixture_dir.glob("sample_*.csv")):
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hashes

    def _market_dir(self, market: str) -> Path:
        subdir = self.fixture_dir / market
        return subdir if subdir.exists() else self.fixture_dir

    def _read_csv(
        self,
        filename: str,
        market: str = "cn",
        bool_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        path = self._market_dir(market) / filename
        if not path.exists():
            raise FixtureDataError(f"Missing fixture file: {path}")
        df = pd.read_csv(path, dtype={"symbol": "string"})
        if "symbol" in df.columns:
            df["symbol"] = df["symbol"].map(lambda value: normalize_symbol(value, market)).astype("string")
        for column in bool_columns or []:
            if column in df.columns:
                df[column] = df[column].astype(bool)
        return df

    @staticmethod
    def _filter_market(df: pd.DataFrame, market: str) -> pd.DataFrame:
        if "market" not in df.columns:
            return df.copy()
        return df[df["market"] == market].copy()

    @staticmethod
    def _filter_dates(df: pd.DataFrame, start_date: str | None, end_date: str | None) -> pd.DataFrame:
        filtered = df
        if start_date is not None:
            filtered = filtered[filtered["date"] >= start_date]
        if end_date is not None:
            filtered = filtered[filtered["date"] <= end_date]
        return filtered.copy()

    def _filter_date_symbol(
        self,
        df: pd.DataFrame,
        market: str,
        start_date: str | None,
        end_date: str | None,
        symbols: list[str] | None,
    ) -> pd.DataFrame:
        filtered = self._filter_dates(df, start_date, end_date)
        if symbols is not None:
            wanted = {normalize_symbol(symbol, market) for symbol in symbols}
            filtered = filtered[filtered["symbol"].isin(wanted)]
        return filtered.sort_values(["date", "symbol"]).copy()
