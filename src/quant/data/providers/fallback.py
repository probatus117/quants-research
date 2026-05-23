"""Provider fallback chain utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.quant.data.providers.base import QuantDataProvider


@dataclass
class FallbackStatus:
    provider_chain: list[str]
    fallback_status: str
    skip_reason: str = ""
    errors: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_chain": self.provider_chain,
            "fallback_status": self.fallback_status,
            "skip_reason": self.skip_reason,
            "errors": self.errors,
        }


class FallbackProvider(QuantDataProvider):
    """Try providers in order and attach provider-chain status to outputs."""

    def __init__(self, providers: list[QuantDataProvider]) -> None:
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider")
        self.providers = providers
        self.last_status = FallbackStatus(provider_chain=self._provider_names(), fallback_status="primary")

    def _provider_names(self) -> list[str]:
        return [str(getattr(provider, "provider_name", provider.__class__.__name__)) for provider in self.providers]

    def _call(self, method: str, *args: Any, **kwargs: Any) -> pd.DataFrame:
        errors: dict[str, str] = {}
        for index, provider in enumerate(self.providers):
            name = str(getattr(provider, "provider_name", provider.__class__.__name__))
            try:
                result = getattr(provider, method)(*args, **kwargs)
            except Exception as exc:
                errors[name] = str(exc)
                continue
            status = "primary" if index == 0 else "fallback"
            self.last_status = FallbackStatus(self._provider_names(), status, errors=errors)
            result.attrs["provider_status"] = self.last_status.as_dict()
            return result
        reason = "; ".join(f"{name}: {message}" for name, message in errors.items())
        self.last_status = FallbackStatus(self._provider_names(), "skipped", skip_reason=reason, errors=errors)
        raise RuntimeError(f"All quant data providers failed: {reason}")

    def get_daily_bar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        return self._call("get_daily_bar", market=market, start_date=start_date, end_date=end_date, symbols=symbols)

    def get_daily_basic(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None, symbols: list[str] | None = None) -> pd.DataFrame:
        return self._call("get_daily_basic", market=market, start_date=start_date, end_date=end_date, symbols=symbols)

    def get_calendar(self, market: str = "cn", start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        return self._call("get_calendar", market=market, start_date=start_date, end_date=end_date)

    def get_universe(self, market: str = "cn", universe: str = "sample_a") -> pd.DataFrame:
        return self._call("get_universe", market=market, universe=universe)

    def get_index_member(self, market: str, index_code: str) -> pd.DataFrame:
        return self._call("get_index_member", market=market, index_code=index_code)

    def get_benchmark_return(self, market: str, index_code: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        return self._call(
            "get_benchmark_return",
            market=market,
            index_code=index_code,
            start_date=start_date,
            end_date=end_date,
        )
