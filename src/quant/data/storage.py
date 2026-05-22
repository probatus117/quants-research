"""Parquet storage helpers for quant data artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_PARQUET_ROOT = Path("data/quant/parquet")


class QuantStorageError(ValueError):
    """Raised when quant storage cannot read or write a table."""


def table_path(table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> Path:
    if not table_name or "/" in table_name or ".." in table_name:
        raise QuantStorageError(f"Invalid table name: {table_name!r}")
    return Path(root) / table_name


def write_parquet(df: pd.DataFrame, table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> Path:
    """Write a DataFrame to data/quant/parquet/{table_name}/data.parquet."""
    path = table_path(table_name, root)
    path.mkdir(parents=True, exist_ok=True)
    output = path / "data.parquet"
    df.to_parquet(output, index=False)
    return output


def read_parquet(table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> pd.DataFrame:
    """Read a DataFrame from data/quant/parquet/{table_name}/data.parquet."""
    path = table_path(table_name, root) / "data.parquet"
    if not path.exists():
        raise QuantStorageError(f"Parquet table not found: {path}")
    return pd.read_parquet(path)
