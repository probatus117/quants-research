"""yfinance provider for US/JP/CN benchmark-oriented quant data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.data.providers.base import QuantDataProvider
from src.quant.data.schema import normalize_symbol, validate_schema

try:  # pragma: no cover - availability is environment-specific.
    import yfinance as yf

    HAS_YFINANCE = True
except ImportError:  # pragma: no cover - exercised by tests via monkeypatch.
    yf = None
    HAS_YFINANCE = False


class YFinanceProviderError(RuntimeError):
    """Raised when yfinance cannot provide usable data."""


@dataclass
class ProviderStatus:
    provider_chain: list[str] = field(default_factory=lambda: ["yfinance"])
    fallback_status: str = "primary"
    skip_reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_chain": self.provider_chain,
            "fallback_status": self.fallback_status,
            "skip_reason": self.skip_reason,
        }


class YFinanceProvider(QuantDataProvider):
    """Fetch and standardize daily bars through yfinance."""

    def __init__(self, auto_adjust: bool = False) -> None:
        self.auto_adjust = auto_adjust
        self.last_status = ProviderStatus()

    def _set_skipped(self, reason: str) -> None:
        self.last_status = ProviderStatus(fallback_status="skipped", skip_reason=reason)

    def _download(self, symbols: list[str], start_date: str | None, end_date: str | None) -> pd.DataFrame:
        if not HAS_YFINANCE or yf is None:
            self._set_skipped("yfinance is not installed")
            raise YFinanceProviderError(self.last_status.skip_reason)
        try:
            data = yf.download(
                tickers=symbols,
                start=start_date,
                end=end_date,
                group_by="ticker",
                auto_adjust=self.auto_adjust,
                actions=True,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # pragma: no cover - exact exception depends on yfinance/network.
            self._set_skipped(f"yfinance download failed: {exc}")
            raise YFinanceProviderError(self.last_status.skip_reason) from exc
        if data is None or data.empty:
            self._set_skipped("yfinance returned empty data")
            raise YFinanceProviderError(self.last_status.skip_reason)
        self.last_status = ProviderStatus()
        return data

    def get_daily_bar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        market = normalize_market(market)
        cfg = get_market_config(market)
        normalized = [normalize_symbol(symbol, market) for symbol in (symbols or [cfg.benchmark_symbol])]
        download_symbols = [_to_yfinance_symbol(symbol, market) for symbol in normalized]
        raw = self._download(download_symbols, start_date, end_date)
        rows: list[dict[str, Any]] = []
        for symbol, download_symbol in zip(normalized, download_symbols, strict=True):
            frame = _select_symbol_frame(raw, download_symbol, len(normalized))
            required = {"Open", "High", "Low", "Close", "Volume"}
            missing = sorted(required - set(frame.columns))
            if missing:
                self._set_skipped(f"yfinance missing columns for {symbol}: {', '.join(missing)}")
                raise YFinanceProviderError(self.last_status.skip_reason)
            adj = frame["Adj Close"] if "Adj Close" in frame.columns else frame["Close"]
            for date, row in frame.iterrows():
                close = float(row["Close"])
                volume = float(row["Volume"] or 0.0)
                rows.append(
                    {
                        "date": pd.Timestamp(date).date().isoformat(),
                        "market": market,
                        "symbol": symbol,
                        "exchange": cfg.exchanges[0],
                        "currency": cfg.currency,
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": close,
                        "adj_close": float(adj.loc[date] if hasattr(adj, "loc") else adj),
                        "volume": volume,
                        "amount": close * volume,
                        "is_suspended": bool(volume == 0),
                    }
                )
        if not rows:
            self._set_skipped("yfinance standardized to zero rows")
            raise YFinanceProviderError(self.last_status.skip_reason)
        df = pd.DataFrame(rows)
        df.attrs["provider_status"] = self.last_status.as_dict()
        return validate_schema(df, "daily_bar")

    def get_daily_basic(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        self._set_skipped("yfinance daily_basic fields are not complete enough for Phase 7 P0")
        return pd.DataFrame(
            columns=[
                "date",
                "market",
                "symbol",
                "currency",
                "pe_ttm",
                "pb",
                "total_mv",
                "circ_mv",
                "total_share",
                "float_share",
                "dividend_yield",
                "turnover_rate",
            ]
        )

    def get_calendar(
        self,
        market: str = "cn",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        bars = self.get_daily_bar(market=market, start_date=start_date, end_date=end_date)
        calendar = bars[["date", "market"]].drop_duplicates().sort_values("date").copy()
        calendar["is_open"] = True
        return validate_schema(calendar.reset_index(drop=True), "calendar")

    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        market = normalize_market(market)
        cfg = get_market_config(market)
        symbol = normalize_symbol(cfg.benchmark_symbol, market)
        self._set_skipped("yfinance universe is benchmark-only best effort")
        return validate_schema(
            pd.DataFrame(
                [
                    {
                        "market": market,
                        "symbol": symbol,
                        "name": symbol,
                        "exchange": cfg.exchanges[0],
                        "currency": cfg.currency,
                        "industry": "Unknown",
                        "market_cap_bucket": "unknown",
                        "list_date": "1900-01-01",
                        "delist_date": "",
                        "universe": universe,
                        "is_member": True,
                    }
                ]
            ),
            "dim_security",
        )

    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        self._set_skipped("yfinance does not provide reliable index membership")
        return pd.DataFrame(columns=["market", "index_code", "symbol", "universe", "is_member"])

    def get_benchmark_return(
        self,
        market: str,
        index_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        bars = self.get_daily_bar(market=market, start_date=start_date, end_date=end_date, symbols=[index_code])
        returns = bars.sort_values("date")["adj_close"].pct_change().fillna(0.0)
        output = bars[["date", "market"]].copy()
        output["index_code"] = index_code
        output["benchmark_return"] = returns.to_numpy()
        output.attrs["provider_status"] = self.last_status.as_dict()
        return output


def _select_symbol_frame(raw: pd.DataFrame, symbol: str, symbol_count: int) -> pd.DataFrame:
    """Extract one ticker frame from yfinance's single or MultiIndex result."""
    if isinstance(raw.columns, pd.MultiIndex):
        if symbol in raw.columns.get_level_values(0):
            return raw[symbol].dropna(how="all")
        if symbol in raw.columns.get_level_values(-1):
            return raw.xs(symbol, level=-1, axis=1).dropna(how="all")
    if symbol_count == 1:
        return raw.dropna(how="all")
    return pd.DataFrame()


def _to_yfinance_symbol(symbol: str, market: str) -> str:
    """Map normalized symbols to yfinance ticker notation."""
    if market == "us":
        return symbol.replace(".", "-")
    return symbol
