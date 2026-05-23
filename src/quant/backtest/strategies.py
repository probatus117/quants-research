"""Strategy interfaces for pandas backtests."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Selection and weighting contract used by the pandas runner."""

    @abstractmethod
    def select(self, signal: pd.DataFrame, date: pd.Timestamp, top_n: int) -> list[str]:
        """Return selected symbols for a rebalance date."""

    @abstractmethod
    def weight(self, selected: list[str], signal: pd.DataFrame, date: pd.Timestamp) -> dict[str, float]:
        """Return target weights for selected symbols."""


class TopNEqualWeight(BaseStrategy):
    """Default strategy: top-N by score, equal weight."""

    def select(self, signal: pd.DataFrame, date: pd.Timestamp, top_n: int) -> list[str]:
        _ = date
        if signal.empty or top_n <= 0:
            return []
        return signal.head(top_n)["symbol"].astype(str).tolist()

    def weight(self, selected: list[str], signal: pd.DataFrame, date: pd.Timestamp) -> dict[str, float]:
        _ = signal, date
        if not selected:
            return {}
        weight = 1.0 / len(selected)
        return {symbol: weight for symbol in selected}
