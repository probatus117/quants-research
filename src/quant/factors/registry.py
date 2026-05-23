"""Factor registry and YAML config helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Type

from src.quant.config import load_yaml_config
from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.factors.base import BaseFactor, FactorConfig
from src.quant.factors.low_volatility import LowVolatility60DFactor
from src.quant.factors.momentum import Momentum121Factor
from src.quant.factors.value import ValueBPFactor


@dataclass(frozen=True)
class FactorSpec:
    """Resolved factor implementation and market-specific params."""

    name: str
    factor_cls: Type[BaseFactor]
    source_table: str
    enabled: bool = True
    direction: int = 1
    params: dict[str, object] | None = None

    def build(self, universe: str = "sample_a") -> BaseFactor:
        return self.factor_cls(
            FactorConfig(
                name=self.name,
                direction=self.direction,
                universe=universe,
                params=dict(self.params or {}),
            )
        )


FACTOR_REGISTRY: dict[str, tuple[Type[BaseFactor], str]] = {
    "value_bp": (ValueBPFactor, "daily_basic"),
    "momentum_12_1": (Momentum121Factor, "daily_bar"),
    "lowvol_60d": (LowVolatility60DFactor, "daily_bar"),
}


def available_factor_names() -> list[str]:
    """Return registered factor names."""
    return sorted(FACTOR_REGISTRY)


def _default_params(name: str, market: str) -> dict[str, object]:
    market_cfg = get_market_config(market)
    if name == "momentum_12_1":
        return {
            "lookback_days": market_cfg.momentum_lookback_days,
            "skip_days": market_cfg.momentum_skip_days,
        }
    if name == "lowvol_60d":
        return {"window_days": market_cfg.lowvol_window_days}
    return {}


def load_factor_specs(
    config_path: str | Path = "config/quant_factors.yaml",
    market: str = "cn",
    names: list[str] | None = None,
) -> list[FactorSpec]:
    """Resolve enabled factors from YAML into concrete FactorSpec objects."""
    market = normalize_market(market)
    raw = load_yaml_config(config_path)
    factors = raw.get("factors", [])
    if not isinstance(factors, list):
        raise ValueError("quant_factors.yaml: factors must be a list")

    wanted = set(names or available_factor_names())
    specs: list[FactorSpec] = []
    for item in factors:
        if not isinstance(item, dict):
            raise ValueError("quant_factors.yaml: each factor must be a mapping")
        name = str(item.get("name", ""))
        if name not in wanted:
            continue
        if name not in FACTOR_REGISTRY:
            raise ValueError(f"Unknown factor: {name}")
        factor_cls, source_table = FACTOR_REGISTRY[name]
        market_params = item.get("markets", {}).get(market, {}) if isinstance(item.get("markets", {}), dict) else {}
        params = {**_default_params(name, market), **dict(market_params.get("params", {}))}
        specs.append(
            FactorSpec(
                name=name,
                factor_cls=factor_cls,
                source_table=str(item.get("source_table", source_table)),
                enabled=bool(item.get("enabled", True) and market_params.get("enabled", True)),
                direction=int(item.get("direction", getattr(factor_cls, "direction", 1))),
                params=params,
            )
        )

    missing = wanted.difference({spec.name for spec in specs})
    if missing:
        raise ValueError(f"Factors missing from config: {', '.join(sorted(missing))}")
    return [spec for spec in specs if spec.enabled]
