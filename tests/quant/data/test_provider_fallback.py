from __future__ import annotations

import pandas as pd
import pytest

from src.quant.data.providers.fallback import FallbackProvider


class _FailingProvider:
    provider_name = "primary"

    def get_daily_bar(self, **kwargs):
        raise RuntimeError("primary failed")


class _WorkingProvider:
    provider_name = "backup"

    def get_daily_bar(self, **kwargs):
        return pd.DataFrame({"date": ["2024-01-02"], "market": [kwargs["market"]], "symbol": ["AAPL"]})


def test_fallback_provider_uses_backup_and_records_status() -> None:
    provider = FallbackProvider([_FailingProvider(), _WorkingProvider()])

    result = provider.get_daily_bar(market="us")

    assert result.attrs["provider_status"]["fallback_status"] == "fallback"
    assert result.attrs["provider_status"]["provider_chain"] == ["primary", "backup"]
    assert "primary" in result.attrs["provider_status"]["errors"]


def test_fallback_provider_raises_when_all_fail() -> None:
    provider = FallbackProvider([_FailingProvider()])

    with pytest.raises(RuntimeError):
        provider.get_daily_bar(market="cn")

    assert provider.last_status.fallback_status == "skipped"
    assert "primary failed" in provider.last_status.skip_reason
