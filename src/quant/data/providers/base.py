"""Provider abstractions for quant market data."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class QuantDataProvider(ABC):
    """Abstract interface implemented by all quant data providers."""

    @abstractmethod
    def get_daily_bar(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return standardized daily OHLCV bars."""

    @abstractmethod
    def get_daily_basic(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return standardized daily valuation/basic fields."""

    @abstractmethod
    def get_calendar(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return trading calendar rows."""

    @abstractmethod
    def get_universe(self, universe: str = "sample_a") -> pd.DataFrame:
        """Return standardized security universe membership/dimension rows."""
