"""Deterministic hashing for quant experiment inputs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any


def _normalise(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalise(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _normalise(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, set):
        return [_normalise(item) for item in sorted(value, key=str)]
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_payload(config: dict[str, Any], data_version: dict[str, Any]) -> str:
    """Return a stable JSON payload for config + data version."""
    payload = {
        "config": _normalise(config),
        "data_version": _normalise(data_version),
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def calculate_config_hash(config: dict[str, Any], data_version: dict[str, Any]) -> str:
    """Calculate a deterministic SHA256 hash for experiment inputs."""
    return hashlib.sha256(canonical_payload(config, data_version).encode("utf-8")).hexdigest()


def short_config_hash(config: dict[str, Any], data_version: dict[str, Any], length: int = 10) -> str:
    """Return a short deterministic hash for experiment IDs."""
    if length <= 0:
        raise ValueError("length must be positive")
    return calculate_config_hash(config, data_version)[:length]
