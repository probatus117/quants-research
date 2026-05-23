"""Base interfaces for quant factor computation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.data.storage import write_parquet


class FactorError(ValueError):
    """Raised when factor inputs or outputs are invalid."""


@dataclass(frozen=True)
class FactorConfig:
    """Runtime configuration shared by factor implementations."""

    name: str
    direction: int = 1
    universe: str = "sample_a"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FactorResult:
    """A long-form date-symbol factor result."""

    config: FactorConfig
    values: pd.DataFrame

    @property
    def factor_name(self) -> str:
        return self.config.name


class BaseFactor(ABC):
    """Abstract base class for date-symbol quant factors."""

    factor_name: str
    direction: int = 1
    required_columns: tuple[str, ...] = ("date", "symbol")

    def __init__(self, config: FactorConfig | None = None) -> None:
        self.config = config or FactorConfig(
            name=self.factor_name,
            direction=self.direction,
        )
        if self.config.name != self.factor_name:
            raise FactorError(f"Factor config name {self.config.name!r} does not match {self.factor_name!r}")

    def validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate that input data contains the columns required by this factor."""
        missing = [column for column in self.required_columns if column not in df.columns]
        if missing:
            raise FactorError(f"{self.factor_name}: missing required columns: {', '.join(missing)}")
        if df.empty:
            raise FactorError(f"{self.factor_name}: input table is empty")
        return df

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> FactorResult:
        """Compute raw factor values from an input DataFrame."""

    def build_result(self, values: pd.DataFrame, raw_column: str = "raw_value") -> FactorResult:
        """Build a standard FactorResult from date-symbol raw values."""
        required = {"date", "symbol", raw_column}
        missing = required.difference(values.columns)
        if missing:
            raise FactorError(f"{self.factor_name}: result missing columns: {', '.join(sorted(missing))}")

        identity_columns = ["date", "symbol"]
        if "market" in values.columns:
            identity_columns.insert(1, "market")
        output = values[identity_columns + [raw_column]].copy()
        output = output.rename(columns={raw_column: "raw_value"})
        output["factor_name"] = self.factor_name
        output["direction"] = self.config.direction
        output["universe"] = self.config.universe
        columns = [*identity_columns, "factor_name", "raw_value", "direction", "universe"]
        output = output[columns].sort_values(identity_columns).reset_index(drop=True)
        return FactorResult(config=self.config, values=output)

    def save(self, result: FactorResult, root: str | Path, table_name: str = "factor_value") -> Path:
        """Persist factor values to a parquet table."""
        if result.factor_name != self.factor_name:
            raise FactorError(f"Cannot save {result.factor_name!r} with {self.factor_name!r}")
        return write_parquet(result.values, table_name=table_name, root=root)
