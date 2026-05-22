"""Standard quant data schemas and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype, is_string_dtype


class SchemaValidationError(ValueError):
    """Raised when a quant data table does not match its standard schema."""


@dataclass(frozen=True)
class TableSchema:
    """A lightweight schema definition for DataFrame validation."""

    name: str
    required_fields: tuple[str, ...]
    dtype_kinds: dict[str, str]
    date_fields: tuple[str, ...] = ("date",)


DAILY_BAR_SCHEMA = TableSchema(
    name="daily_bar",
    required_fields=(
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "amount",
        "is_suspended",
    ),
    dtype_kinds={
        "date": "date",
        "symbol": "string",
        "open": "numeric",
        "high": "numeric",
        "low": "numeric",
        "close": "numeric",
        "adj_close": "numeric",
        "volume": "numeric",
        "amount": "numeric",
        "is_suspended": "bool",
    },
)

DAILY_BASIC_SCHEMA = TableSchema(
    name="daily_basic",
    required_fields=(
        "date",
        "symbol",
        "pe_ttm",
        "pb",
        "total_mv",
        "circ_mv",
        "turnover_rate",
    ),
    dtype_kinds={
        "date": "date",
        "symbol": "string",
        "pe_ttm": "numeric",
        "pb": "numeric",
        "total_mv": "numeric",
        "circ_mv": "numeric",
        "turnover_rate": "numeric",
    },
)

DIM_SECURITY_SCHEMA = TableSchema(
    name="dim_security",
    required_fields=(
        "symbol",
        "name",
        "exchange",
        "industry",
        "market_cap_bucket",
        "list_date",
        "universe",
        "is_member",
    ),
    dtype_kinds={
        "symbol": "string",
        "name": "string",
        "exchange": "string",
        "industry": "string",
        "market_cap_bucket": "string",
        "list_date": "date",
        "universe": "string",
        "is_member": "bool",
    },
    date_fields=("list_date",),
)

CALENDAR_SCHEMA = TableSchema(
    name="calendar",
    required_fields=("date", "is_open"),
    dtype_kinds={"date": "date", "is_open": "bool"},
)

UNIVERSE_MEMBER_SCHEMA = TableSchema(
    name="universe_member",
    required_fields=("universe", "date", "symbol", "is_member"),
    dtype_kinds={
        "universe": "string",
        "date": "date",
        "symbol": "string",
        "is_member": "bool",
    },
)

SCHEMAS: dict[str, TableSchema] = {
    schema.name: schema
    for schema in (
        DAILY_BAR_SCHEMA,
        DAILY_BASIC_SCHEMA,
        DIM_SECURITY_SCHEMA,
        CALENDAR_SCHEMA,
        UNIVERSE_MEMBER_SCHEMA,
    )
}


def _require_columns(df: pd.DataFrame, schema: TableSchema) -> None:
    missing = [field for field in schema.required_fields if field not in df.columns]
    if missing:
        raise SchemaValidationError(f"{schema.name}: missing required fields: {', '.join(missing)}")


def _validate_date_series(series: pd.Series, field: str, table_name: str) -> None:
    as_text = series.astype("string")
    bad_format = ~as_text.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
    if bad_format.any():
        examples = as_text[bad_format].head(3).tolist()
        raise SchemaValidationError(f"{table_name}.{field}: invalid YYYY-MM-DD values: {examples}")
    parsed = pd.to_datetime(as_text, format="%Y-%m-%d", errors="coerce")
    if parsed.isna().any():
        examples = as_text[parsed.isna()].head(3).tolist()
        raise SchemaValidationError(f"{table_name}.{field}: invalid calendar dates: {examples}")


def _validate_dtype_kind(series: pd.Series, expected: str, field: str, table_name: str) -> None:
    if expected == "date":
        _validate_date_series(series, field, table_name)
        return
    if expected == "string":
        if not (is_string_dtype(series) or series.dtype == object):
            raise SchemaValidationError(f"{table_name}.{field}: expected string-like dtype, got {series.dtype}")
        if series.isna().any():
            raise SchemaValidationError(f"{table_name}.{field}: contains null values")
        return
    if expected == "numeric":
        if not is_numeric_dtype(series):
            raise SchemaValidationError(f"{table_name}.{field}: expected numeric dtype, got {series.dtype}")
        return
    if expected == "bool":
        if not is_bool_dtype(series):
            raise SchemaValidationError(f"{table_name}.{field}: expected bool dtype, got {series.dtype}")
        return
    raise SchemaValidationError(f"{table_name}.{field}: unknown expected dtype kind: {expected}")


def validate_schema(df: pd.DataFrame, schema: TableSchema | str) -> pd.DataFrame:
    """Validate required fields, dtypes, date format, duplicates, and table invariants."""
    schema_obj = SCHEMAS[schema] if isinstance(schema, str) else schema
    if df.empty:
        raise SchemaValidationError(f"{schema_obj.name}: table is empty")
    _require_columns(df, schema_obj)
    for field, expected in schema_obj.dtype_kinds.items():
        _validate_dtype_kind(df[field], expected, field, schema_obj.name)

    if {"date", "symbol"}.issubset(df.columns):
        duplicate_mask = df.duplicated(["date", "symbol"])
        if duplicate_mask.any():
            raise SchemaValidationError(f"{schema_obj.name}: duplicate date-symbol rows: {int(duplicate_mask.sum())}")

    if schema_obj.name == "daily_bar":
        validate_ohlc(df)
    if schema_obj.name == "daily_basic":
        _validate_non_negative(df, ["total_mv", "circ_mv", "turnover_rate"], schema_obj.name)
    if schema_obj.name == "calendar" and df["date"].duplicated().any():
        raise SchemaValidationError("calendar: duplicate date rows")
    return df


def validate_ohlc(df: pd.DataFrame) -> None:
    """Validate OHLC prices, adjusted close, volume, and amount boundaries."""
    price_cols = ["open", "high", "low", "close", "adj_close"]
    if (df[price_cols] <= 0).any().any():
        raise SchemaValidationError("daily_bar: OHLC/adj_close must be positive")
    if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any():
        raise SchemaValidationError("daily_bar: high is below open/close/low for at least one row")
    if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
        raise SchemaValidationError("daily_bar: low is above open/close/high for at least one row")
    _validate_non_negative(df, ["volume", "amount"], "daily_bar")


def _validate_non_negative(df: pd.DataFrame, columns: list[str], table_name: str) -> None:
    for column in columns:
        if (df[column] < 0).any():
            raise SchemaValidationError(f"{table_name}.{column}: contains negative values")


def validate_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Validate all known tables included in a mapping."""
    validated: dict[str, pd.DataFrame] = {}
    for name, df in tables.items():
        if name not in SCHEMAS:
            raise SchemaValidationError(f"Unknown quant table schema: {name}")
        validated[name] = validate_schema(df, name)
    return validated


def normalize_symbol(value: Any) -> str:
    """Normalize A-share symbols while preserving leading zeroes."""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text
