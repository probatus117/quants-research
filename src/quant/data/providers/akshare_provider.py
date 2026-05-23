"""Optional AKShare provider skeleton with graceful degradation."""

from __future__ import annotations

import pandas as pd

from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.data.providers.base import QuantDataProvider
from src.quant.data.schema import normalize_symbol, validate_schema

try:  # pragma: no cover - environment-specific.
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:  # pragma: no cover
    ak = None
    HAS_AKSHARE = False


class ProviderUnavailableError(RuntimeError):
    """Raised when an optional provider cannot serve a request."""


class AkshareProvider(QuantDataProvider):
    """AKShare adapter placeholder for Phase 7a fallback chains."""

    provider_name = "akshare"

    def _unavailable(self) -> ProviderUnavailableError:
        reason = "akshare is not installed" if not HAS_AKSHARE else "akshare adapter is not configured"
        return ProviderUnavailableError(reason)

    def get_daily_bar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        market = normalize_market(market)
        if market != "cn" or not HAS_AKSHARE or ak is None:
            raise self._unavailable()
        cfg = get_market_config(market)
        rows = []
        for symbol in symbols or []:
            normalized = normalize_symbol(symbol, market)
            raw = ak.stock_zh_a_hist(
                symbol=normalized,
                period="daily",
                start_date=(start_date or "").replace("-", ""),
                end_date=(end_date or "").replace("-", ""),
                adjust="qfq",
            )
            if raw is None or raw.empty:
                continue
            for _, row in raw.iterrows():
                close = float(row["收盘"])
                volume = float(row.get("成交量", 0.0))
                rows.append(
                    {
                        "date": pd.Timestamp(row["日期"]).date().isoformat(),
                        "market": market,
                        "symbol": normalized,
                        "exchange": "SH" if normalized.startswith("6") else "SZ",
                        "currency": cfg.currency,
                        "open": float(row["开盘"]),
                        "high": float(row["最高"]),
                        "low": float(row["最低"]),
                        "close": close,
                        "adj_close": close,
                        "volume": volume,
                        "amount": float(row.get("成交额", close * volume)),
                        "is_suspended": bool(volume == 0),
                    }
                )
        if not rows:
            raise ProviderUnavailableError("akshare returned no daily_bar rows")
        return validate_schema(pd.DataFrame(rows), "daily_bar")

    def get_daily_basic(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        market = normalize_market(market)
        if market != "cn" or not HAS_AKSHARE or ak is None:
            raise self._unavailable()
        # AKShare daily valuation coverage varies by endpoint; expose a clear skip until mapped.
        raise ProviderUnavailableError("akshare daily_basic mapping is not available in this environment")

    def get_calendar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        bars = self.get_daily_bar(market=market, start_date=start_date, end_date=end_date, symbols=["000001"])
        calendar = bars[["date", "market"]].drop_duplicates().copy()
        calendar["is_open"] = True
        return validate_schema(calendar, "calendar")

    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        market = normalize_market(market)
        if market != "cn" or not HAS_AKSHARE or ak is None:
            raise self._unavailable()
        cfg = get_market_config(market)
        raw = ak.stock_info_a_code_name()
        rows = []
        for _, row in raw.iterrows():
            symbol = normalize_symbol(row["code"], market)
            rows.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "name": str(row["name"]),
                    "exchange": "SH" if symbol.startswith("6") else "SZ",
                    "currency": cfg.currency,
                    "industry": "Unknown",
                    "market_cap_bucket": "unknown",
                    "list_date": "1900-01-01",
                    "delist_date": "",
                    "universe": universe,
                    "is_member": True,
                }
            )
        return validate_schema(pd.DataFrame(rows), "dim_security")

    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        market = normalize_market(market)
        if market != "cn" or not HAS_AKSHARE or ak is None:
            raise self._unavailable()
        try:
            raw = ak.index_stock_cons(symbol=index_code)
        except Exception as exc:
            raise ProviderUnavailableError(f"akshare index member mapping failed: {exc}") from exc
        code_col = "品种代码" if "品种代码" in raw.columns else raw.columns[0]
        output = pd.DataFrame(
            {
                "market": market,
                "index_code": index_code,
                "symbol": raw[code_col].map(lambda value: normalize_symbol(value, market)),
                "universe": index_code,
                "is_member": True,
            }
        )
        return output

    def get_benchmark_return(self, market: str, index_code: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        market = normalize_market(market)
        if market != "cn" or not HAS_AKSHARE or ak is None:
            raise self._unavailable()
        symbol = index_code
        if index_code == "csi300":
            symbol = "000300"
        try:
            raw = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}" if not str(symbol).startswith(("sh", "sz")) else symbol)
        except Exception as exc:
            raise ProviderUnavailableError(f"akshare benchmark mapping failed: {exc}") from exc
        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
        if start_date is not None:
            frame = frame[frame["date"] >= start_date]
        if end_date is not None:
            frame = frame[frame["date"] <= end_date]
        returns = pd.to_numeric(frame["close"], errors="coerce").pct_change().fillna(0.0)
        return pd.DataFrame(
            {
                "date": frame["date"],
                "market": market,
                "index_code": index_code,
                "benchmark_return": returns,
            }
        )
