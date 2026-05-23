"""Provider abstractions for quant market data."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class QuantDataProvider(ABC):
    """Abstract interface implemented by all quant data providers."""

    @abstractmethod
    def get_daily_bar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return standardized daily OHLCV bars."""

    @abstractmethod
    def get_daily_basic(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return standardized daily valuation/basic fields."""

    @abstractmethod
    def get_calendar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return trading calendar rows."""

    @abstractmethod
    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        """Return standardized security universe membership/dimension rows."""

    @abstractmethod
    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        """Return standardized index membership rows when available."""

    @abstractmethod
    def get_benchmark_return(
        self,
        market: str,
        index_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return benchmark daily returns with date, market, index_code, and benchmark_return."""
