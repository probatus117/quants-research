from __future__ import annotations

import pandas as pd
import pytest

import src.quant.data.providers.yfinance_provider as yfinance_provider
from src.quant.data.providers.yfinance_provider import YFinanceProvider, YFinanceProviderError


class _FakeYF:
    def __init__(self, payload):
        self.payload = payload

    def download(self, **kwargs):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _CapturingYF(_FakeYF):
    def __init__(self, payload):
        super().__init__(payload)
        self.last_kwargs = None

    def download(self, **kwargs):
        self.last_kwargs = kwargs
        return super().download(**kwargs)


def _ohlcv_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [10.0, 10.5],
            "High": [10.6, 10.9],
            "Low": [9.9, 10.4],
            "Close": [10.4, 10.8],
            "Adj Close": [10.4, 10.8],
            "Volume": [1000, 1200],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )


def test_yfinance_provider_maps_daily_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "HAS_YFINANCE", True)
    monkeypatch.setattr(yfinance_provider, "yf", _FakeYF(_ohlcv_frame()))

    bars = YFinanceProvider().get_daily_bar(market="us", symbols=["aapl"])

    assert bars["symbol"].tolist() == ["AAPL", "AAPL"]
    assert bars["market"].eq("us").all()
    assert bars["currency"].eq("USD").all()
    assert bars.attrs["provider_status"]["fallback_status"] == "primary"


def test_yfinance_provider_uses_yahoo_symbol_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _CapturingYF(_ohlcv_frame())
    monkeypatch.setattr(yfinance_provider, "HAS_YFINANCE", True)
    monkeypatch.setattr(yfinance_provider, "yf", fake)

    bars = YFinanceProvider().get_daily_bar(market="us", symbols=["BRK.B"])

    assert fake.last_kwargs["tickers"] == ["BRK-B"]
    assert bars["symbol"].iloc[0] == "BRK.B"


def test_yfinance_provider_empty_response_sets_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "HAS_YFINANCE", True)
    monkeypatch.setattr(yfinance_provider, "yf", _FakeYF(pd.DataFrame()))
    provider = YFinanceProvider()

    with pytest.raises(YFinanceProviderError):
        provider.get_daily_bar(market="us", symbols=["AAPL"])

    assert provider.last_status.fallback_status == "skipped"
    assert "empty" in provider.last_status.skip_reason


def test_yfinance_provider_missing_column_sets_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "HAS_YFINANCE", True)
    monkeypatch.setattr(yfinance_provider, "yf", _FakeYF(_ohlcv_frame().drop(columns=["High"])))
    provider = YFinanceProvider()

    with pytest.raises(YFinanceProviderError):
        provider.get_daily_bar(market="jp", symbols=["7203"])

    assert "missing columns" in provider.last_status.skip_reason


def test_yfinance_provider_import_missing_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "HAS_YFINANCE", False)
    monkeypatch.setattr(yfinance_provider, "yf", None)
    provider = YFinanceProvider()

    with pytest.raises(YFinanceProviderError):
        provider.get_daily_bar(market="us", symbols=["AAPL"])

    assert "not installed" in provider.last_status.skip_reason
