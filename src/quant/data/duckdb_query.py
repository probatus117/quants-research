"""Optional DuckDB adapter for querying quant parquet datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pandas as pd

from src.quant.data.storage import DEFAULT_PARQUET_ROOT, QuantStorageError, table_path

try:  # pragma: no cover - environment-specific.
    import duckdb

    HAS_DUCKDB = True
except ImportError:  # pragma: no cover
    duckdb = None
    HAS_DUCKDB = False


DUCKDB_SKIP_REASON = "duckdb is not installed; falling back to pandas parquet reads"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DuckDBCapability:
    """Runtime availability for the optional DuckDB integration."""

    available: bool
    skip_reason: str | None = None


@dataclass(frozen=True)
class DuckDBQueryResult:
    """DataFrame plus audit metadata for DuckDB/fallback query paths."""

    frame: pd.DataFrame
    engine: str
    sql: str | None = None
    fallback_used: bool = False
    skip_reason: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "sql": self.sql,
            "row_count": int(len(self.frame)),
        }


def check_duckdb_capability() -> DuckDBCapability:
    """Return DuckDB availability without importing callers into hard failures."""

    if HAS_DUCKDB and duckdb is not None:
        return DuckDBCapability(available=True)
    return DuckDBCapability(available=False, skip_reason=DUCKDB_SKIP_REASON)


def _identifier(value: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise QuantStorageError(f"Invalid SQL identifier: {value!r}")
    return value


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _parquet_files(table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> list[Path]:
    path = table_path(table_name, root)
    files = sorted(path.glob("*.parquet"))
    if not files:
        raise QuantStorageError(f"Parquet table not found: {path}")
    return files


def _parquet_glob(table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> str:
    _parquet_files(table_name, root)
    return str(table_path(table_name, root) / "*.parquet")


def _read_parquet_dataset(table_name: str, root: str | Path = DEFAULT_PARQUET_ROOT) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in _parquet_files(table_name, root)]
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True)


def _register_parquet_views(connection: Any, table_names: list[str], root: str | Path) -> None:
    for table_name in table_names:
        identifier = _identifier(table_name)
        parquet_glob = _parquet_glob(table_name, root).replace("'", "''")
        connection.execute(
            f"CREATE OR REPLACE TEMP VIEW {identifier} AS "
            f"SELECT * FROM read_parquet('{parquet_glob}', union_by_name=true)"
        )


def query_sql(
    sql: str,
    table_names: list[str],
    root: str | Path = DEFAULT_PARQUET_ROOT,
) -> DuckDBQueryResult:
    """Execute SQL against parquet tables when DuckDB is available.

    Arbitrary SQL requires DuckDB. When it is unavailable, the call returns an
    empty audited result instead of crashing; use ``query_table`` for pandas
    fallback of simple single-table queries.
    """

    capability = check_duckdb_capability()
    if not capability.available or duckdb is None:
        return DuckDBQueryResult(
            frame=pd.DataFrame(),
            engine="pandas",
            sql=sql,
            fallback_used=True,
            skip_reason=capability.skip_reason or DUCKDB_SKIP_REASON,
        )

    connection = duckdb.connect(database=":memory:")
    try:
        _register_parquet_views(connection, table_names, root)
        frame = connection.execute(sql).fetchdf()
    finally:
        connection.close()
    return DuckDBQueryResult(frame=frame, engine="duckdb", sql=sql)


def _build_where(filters: dict[str, Any] | None) -> str:
    if not filters:
        return ""
    clauses = []
    for column, value in filters.items():
        identifier = _identifier(column)
        if isinstance(value, list | tuple | set | frozenset):
            literals = ", ".join(_literal(item) for item in value)
            clauses.append(f"{identifier} IN ({literals})")
        else:
            clauses.append(f"{identifier} = {_literal(value)}")
    return " WHERE " + " AND ".join(clauses)


def _build_select_sql(
    table_name: str,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
) -> str:
    table = _identifier(table_name)
    selected = "*"
    if columns:
        selected = ", ".join(_identifier(column) for column in columns)
    sql = f"SELECT {selected} FROM {table}{_build_where(filters)}"
    if order_by:
        sql += " ORDER BY " + ", ".join(_identifier(column) for column in order_by)
    if limit is not None:
        if limit < 0:
            raise QuantStorageError("limit must be >= 0")
        sql += f" LIMIT {int(limit)}"
    return sql


def _pandas_query_table(
    table_name: str,
    root: str | Path,
    columns: list[str] | None,
    filters: dict[str, Any] | None,
    order_by: list[str] | None,
    limit: int | None,
) -> pd.DataFrame:
    frame = _read_parquet_dataset(table_name, root)
    for column, value in (filters or {}).items():
        if isinstance(value, list | tuple | set | frozenset):
            frame = frame[frame[column].isin(list(value))]
        else:
            frame = frame[frame[column] == value]
    if columns:
        frame = frame[columns]
    if order_by:
        frame = frame.sort_values(order_by)
    if limit is not None:
        frame = frame.head(limit)
    return frame.reset_index(drop=True)


def query_table(
    table_name: str,
    root: str | Path = DEFAULT_PARQUET_ROOT,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
    prefer_duckdb: bool = True,
) -> DuckDBQueryResult:
    """Query one parquet table with DuckDB, or pandas when DuckDB is absent."""

    sql = _build_select_sql(table_name, columns=columns, filters=filters, order_by=order_by, limit=limit)
    capability = check_duckdb_capability()
    if prefer_duckdb and capability.available:
        return query_sql(sql, table_names=[table_name], root=root)

    frame = _pandas_query_table(table_name, root, columns, filters, order_by, limit)
    skip_reason = capability.skip_reason if prefer_duckdb else "duckdb disabled by caller; using pandas parquet reads"
    return DuckDBQueryResult(
        frame=frame,
        engine="pandas",
        sql=sql,
        fallback_used=prefer_duckdb,
        skip_reason=skip_reason,
    )


def build_universe(
    root: str | Path = DEFAULT_PARQUET_ROOT,
    market: str = "cn",
    universe: str | None = "sample_a",
    as_of_date: str | None = None,
    min_total_mv: float | None = None,
    prefer_duckdb: bool = True,
) -> DuckDBQueryResult:
    """Build a research universe from parquet tables using SQL semantics."""

    filters: dict[str, Any] = {"market": market, "is_member": True}
    if universe is not None:
        filters["universe"] = universe

    if min_total_mv is None:
        return query_table(
            "dim_security",
            root=root,
            filters=filters,
            order_by=["symbol"],
            prefer_duckdb=prefer_duckdb,
        )

    sql = (
        "SELECT DISTINCT d.* "
        "FROM dim_security d "
        "JOIN daily_basic b "
        "ON d.market = b.market AND d.symbol = b.symbol "
        f"WHERE d.market = {_literal(market)} AND d.is_member = TRUE "
        f"AND b.total_mv >= {_literal(float(min_total_mv))}"
    )
    if universe is not None:
        sql += f" AND d.universe = {_literal(universe)}"
    if as_of_date is not None:
        sql += f" AND b.date <= {_literal(as_of_date)}"
    sql += " ORDER BY d.symbol"

    capability = check_duckdb_capability()
    if prefer_duckdb and capability.available:
        return query_sql(sql, table_names=["dim_security", "daily_basic"], root=root)

    dim_security = _pandas_query_table("dim_security", root, None, filters, None, None)
    daily_basic = _read_parquet_dataset("daily_basic", root)
    daily_basic = daily_basic[(daily_basic["market"] == market) & (daily_basic["total_mv"] >= float(min_total_mv))]
    if as_of_date is not None:
        daily_basic = daily_basic[daily_basic["date"] <= as_of_date]
    symbols = set(daily_basic["symbol"].dropna().tolist())
    frame = dim_security[dim_security["symbol"].isin(symbols)].sort_values("symbol").reset_index(drop=True)
    skip_reason = capability.skip_reason if prefer_duckdb else "duckdb disabled by caller; using pandas parquet reads"
    return DuckDBQueryResult(frame=frame, engine="pandas", sql=sql, fallback_used=prefer_duckdb, skip_reason=skip_reason)
