"""Utilities for quant YAML config loading and validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class QuantConfigError(ValueError):
    """Raised when quant config is invalid."""


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file into a dictionary."""
    config_path = Path(path)
    if not config_path.exists():
        raise QuantConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}

    if not isinstance(data, dict):
        raise QuantConfigError(f"Config root must be a mapping: {config_path}")
    return data


def validate_required_fields(config: dict[str, Any], required_fields: list[str]) -> None:
    """Validate required top-level config keys exist and are not empty."""
    missing = [k for k in required_fields if k not in config or config[k] in (None, "", [])]
    if missing:
        raise QuantConfigError(f"Missing required config fields: {', '.join(missing)}")


def config_hash(config: dict[str, Any]) -> str:
    """Return a stable hash for a config dictionary."""
    payload = json.dumps(config, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_and_validate(
    path: str | Path,
    required_fields: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Load config, validate required fields, and return config + hash."""
    config = load_yaml_config(path)
    if required_fields:
        validate_required_fields(config, required_fields)
    return config, config_hash(config)
