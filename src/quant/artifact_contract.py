"""Shared artifact metadata contract for quant outputs."""

from __future__ import annotations

from typing import Any


REQUIRED_ARTIFACT_FIELDS_V0 = ("market", "data_version", "base_currency", "benchmark")
OPTIONAL_ARTIFACT_FIELDS_V1 = ("provider_chain", "fallback_status", "skip_reason")


def validate_artifact_metadata(metadata: dict[str, Any], version: str = "v0") -> list[str]:
    """Return missing required metadata fields for the artifact contract."""
    required = list(REQUIRED_ARTIFACT_FIELDS_V0)
    if version.lower() == "v1":
        required.extend(OPTIONAL_ARTIFACT_FIELDS_V1)
    return [field for field in required if metadata.get(field) in (None, "", [])]


def artifact_metadata(
    market: str,
    data_version: str,
    base_currency: str,
    benchmark: str,
    provider_chain: list[str] | None = None,
    fallback_status: str | None = None,
    skip_reason: str | None = None,
) -> dict[str, Any]:
    """Build normalized artifact metadata used by reports and registries."""
    payload: dict[str, Any] = {
        "market": market,
        "data_version": data_version,
        "base_currency": base_currency,
        "benchmark": benchmark,
    }
    if provider_chain is not None:
        payload["provider_chain"] = provider_chain
    if fallback_status is not None:
        payload["fallback_status"] = fallback_status
    if skip_reason is not None:
        payload["skip_reason"] = skip_reason
    return payload
