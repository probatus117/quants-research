from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.quant.data.schema import SchemaValidationError, validate_schema, validate_tables

FIXTURE_DIR = Path("tests/fixtures/quant")


def _read_csv(name: str, bool_columns: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_csv(FIXTURE_DIR / name, dtype={"symbol": "string"})
    for column in bool_columns or []:
        df[column] = df[column].astype(bool)
    return df


def test_sample_fixtures_pass_schema_validation() -> None:
    tables = {
        "daily_bar": _read_csv("sample_daily_bar.csv", ["is_suspended"]),
        "daily_basic": _read_csv("sample_daily_basic.csv"),
        "calendar": _read_csv("sample_calendar.csv", ["is_open"]),
        "dim_security": _read_csv("sample_universe.csv", ["is_member"]),
    }

    validated = validate_tables(tables)

    assert set(validated) == {"daily_bar", "daily_basic", "calendar", "dim_security"}
    assert len(validated["dim_security"]) == 60
    assert validated["daily_bar"]["date"].min() == "2022-01-03"
    assert validated["daily_bar"]["date"].max() == "2024-12-31"


def test_schema_rejects_missing_required_field() -> None:
    daily_bar = _read_csv("sample_daily_bar.csv", ["is_suspended"]).drop(columns=["adj_close"])

    with pytest.raises(SchemaValidationError, match="missing required fields: adj_close"):
        validate_schema(daily_bar, "daily_bar")


def test_schema_rejects_invalid_ohlc_boundaries() -> None:
    daily_bar = _read_csv("sample_daily_bar.csv", ["is_suspended"]).head(3).copy()
    daily_bar.loc[daily_bar.index[0], "high"] = daily_bar.loc[daily_bar.index[0], "low"] - 0.01

    with pytest.raises(SchemaValidationError, match="high is below"):
        validate_schema(daily_bar, "daily_bar")


def test_schema_rejects_invalid_date_format() -> None:
    calendar = _read_csv("sample_calendar.csv", ["is_open"]).head(3).copy()
    calendar.loc[calendar.index[0], "date"] = "2022/01/01"

    with pytest.raises(SchemaValidationError, match="invalid YYYY-MM-DD"):
        validate_schema(calendar, "calendar")
