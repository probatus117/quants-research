"""Optional Tushare provider skeleton with graceful degradation."""

from __future__ import annotations

import os

import pandas as pd

from src.quant.data.providers.akshare_provider import ProviderUnavailableError
from src.quant.data.providers.base import QuantDataProvider

try:  # pragma: no cover - environment-specific.
    import tushare as ts

    HAS_TUSHARE = True
except ImportError:  # pragma: no cover
    ts = None
    HAS_TUSHARE = False


class TushareProvider(QuantDataProvider):
    """Tushare adapter placeholder for Phase 7a fallback chains."""

    provider_name = "tushare"

    def _unavailable(self) -> ProviderUnavailableError:
        if not HAS_TUSHARE:
            return ProviderUnavailableError("tushare is not installed")
        if not os.environ.get("TUSHARE_TOKEN"):
            return ProviderUnavailableError("TUSHARE_TOKEN is not set")
        return ProviderUnavailableError("tushare adapter is not configured")

    def get_daily_bar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        raise self._unavailable()

    def get_daily_basic(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        raise self._unavailable()

    def get_calendar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        raise self._unavailable()

    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        raise self._unavailable()

    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        raise self._unavailable()

    def get_benchmark_return(self, market: str, index_code: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        raise self._unavailable()
