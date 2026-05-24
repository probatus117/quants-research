from __future__ import annotations

import pandas as pd
import pytest

import src.quant.data.duckdb_query as duckdb_query
from src.quant.data.duckdb_query import build_universe, query_sql, query_table
from src.quant.data.storage import write_parquet


def test_query_table_falls_back_to_pandas_when_duckdb_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-03"],
            "market": ["us", "cn", "us"],
            "symbol": ["AAPL", "000001", "MSFT"],
            "adj_close": [100.0, 10.0, 200.0],
        }
    )
    write_parquet(df, "daily_bar", root=tmp_path)
    monkeypatch.setattr(duckdb_query, "HAS_DUCKDB", False)
    monkeypatch.setattr(duckdb_query, "duckdb", None)

    result = query_table("daily_bar", root=tmp_path, filters={"market": "us"}, order_by=["symbol"])

    assert result.engine == "pandas"
    assert result.fallback_used is True
    assert "duckdb is not installed" in str(result.skip_reason)
    assert result.frame["symbol"].tolist() == ["AAPL", "MSFT"]


def test_query_sql_without_duckdb_returns_audited_skip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_parquet(pd.DataFrame({"market": ["us"], "symbol": ["AAPL"]}), "daily_bar", root=tmp_path)
    monkeypatch.setattr(duckdb_query, "HAS_DUCKDB", False)
    monkeypatch.setattr(duckdb_query, "duckdb", None)

    result = query_sql("SELECT * FROM daily_bar WHERE market = 'us'", ["daily_bar"], root=tmp_path)

    assert result.frame.empty
    assert result.fallback_used is True
    assert "falling back" in str(result.skip_reason)


def test_build_universe_falls_back_to_pandas_with_total_mv_filter(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_parquet(
        pd.DataFrame(
            {
                "market": ["us", "us", "us"],
                "symbol": ["AAPL", "MSFT", "IBM"],
                "name": ["Apple", "Microsoft", "IBM"],
                "exchange": ["NASDAQ", "NASDAQ", "NYSE"],
                "currency": ["USD", "USD", "USD"],
                "industry": ["Tech", "Tech", "Tech"],
                "market_cap_bucket": ["large", "large", "large"],
                "list_date": ["1980-12-12", "1986-03-13", "1911-06-16"],
                "delist_date": ["", "", ""],
                "universe": ["sample_a", "sample_a", "sample_a"],
                "is_member": [True, True, False],
            }
        ),
        "dim_security",
        root=tmp_path,
    )
    write_parquet(
        pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-02", "2024-01-02"],
                "market": ["us", "us", "us"],
                "symbol": ["AAPL", "MSFT", "IBM"],
                "total_mv": [3000.0, 500.0, 4000.0],
            }
        ),
        "daily_basic",
        root=tmp_path,
    )
    monkeypatch.setattr(duckdb_query, "HAS_DUCKDB", False)
    monkeypatch.setattr(duckdb_query, "duckdb", None)

    result = build_universe(root=tmp_path, market="us", min_total_mv=1000.0)

    assert result.engine == "pandas"
    assert result.fallback_used is True
    assert result.frame["symbol"].tolist() == ["AAPL"]


def test_query_table_uses_duckdb_when_available_with_mock(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_parquet(pd.DataFrame({"market": ["us"], "symbol": ["AAPL"]}), "daily_bar", root=tmp_path)
    executed_sql: list[str] = []

    class FakeConnection:
        def execute(self, sql: str):
            executed_sql.append(sql)
            return self

        def fetchdf(self) -> pd.DataFrame:
            return pd.DataFrame({"symbol": ["AAPL"]})

        def close(self) -> None:
            return None

    class FakeDuckDB:
        def connect(self, database: str):
            assert database == ":memory:"
            return FakeConnection()

    monkeypatch.setattr(duckdb_query, "HAS_DUCKDB", True)
    monkeypatch.setattr(duckdb_query, "duckdb", FakeDuckDB())

    result = query_table("daily_bar", root=tmp_path, filters={"market": "us"})

    assert result.engine == "duckdb"
    assert result.fallback_used is False
    assert result.frame["symbol"].tolist() == ["AAPL"]
    assert any("read_parquet" in sql for sql in executed_sql)
    assert executed_sql[-1] == "SELECT * FROM daily_bar WHERE market = 'us'"


@pytest.mark.skipif(not duckdb_query.HAS_DUCKDB, reason="duckdb is not installed")
def test_duckdb_query_reads_appended_parquet_files(tmp_path) -> None:
    write_parquet(
        pd.DataFrame({"date": ["2024-01-02"], "market": ["us"], "symbol": ["AAPL"]}),
        "daily_bar",
        root=tmp_path,
    )
    append_path = tmp_path / "daily_bar" / "append_2024_02.parquet"
    pd.DataFrame({"date": ["2024-02-01"], "market": ["us"], "symbol": ["MSFT"]}).to_parquet(append_path, index=False)

    result = query_table("daily_bar", root=tmp_path, filters={"market": "us"}, order_by=["date"])

    assert result.engine == "duckdb"
    assert result.frame["symbol"].tolist() == ["AAPL", "MSFT"]
