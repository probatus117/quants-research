from __future__ import annotations

import pytest

import src.quant.data.providers.akshare_provider as akshare_provider
import src.quant.data.providers.tushare_provider as tushare_provider
from src.quant.data.providers.akshare_provider import AkshareProvider, ProviderUnavailableError
from src.quant.data.providers.tushare_provider import TushareProvider


def test_akshare_missing_dependency_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(akshare_provider, "HAS_AKSHARE", False)
    monkeypatch.setattr(akshare_provider, "ak", None)

    with pytest.raises(ProviderUnavailableError, match="akshare is not installed"):
        AkshareProvider().get_daily_bar(market="cn", symbols=["000001"])


def test_tushare_missing_dependency_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tushare_provider, "HAS_TUSHARE", False)
    monkeypatch.setattr(tushare_provider, "ts", None)

    with pytest.raises(ProviderUnavailableError, match="tushare is not installed"):
        TushareProvider().get_daily_bar(market="cn", symbols=["000001"])
