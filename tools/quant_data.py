"""Quant data CLI for fixture ingestion and quality checks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.providers.fixture_provider import FixtureDataProvider
from src.quant.data.duckdb_query import build_universe, query_sql, query_table
from src.quant.data.market_config import get_market_config, market_codes, normalize_market
from src.quant.data.qlib_converter import convert_parquet_to_qlib
from src.quant.data.quality_check import dataframe_hash, run_quality_checks
from src.quant.data.storage import write_parquet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant data pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_update = subparsers.add_parser("update", help="Update quant data")
    p_update.add_argument("--source", default="fixture", choices=["fixture"], help="Data source name")
    p_update.add_argument("--fixture-dir", default="tests/fixtures/quant", help="Fixture directory")
    p_update.add_argument("--output-dir", default="data/quant", help="Quant output directory")
    p_update.add_argument("--market", default="cn", choices=[*market_codes(), "all"], help="Market to update")

    p_check = subparsers.add_parser("check", help="Run quant data quality checks")
    p_check.add_argument("--source", default="fixture", choices=["fixture"], help="Data source name")
    p_check.add_argument("--fixture-dir", default="tests/fixtures/quant", help="Fixture directory")
    p_check.add_argument("--market", default="cn", choices=[*market_codes(), "all"], help="Market to check")
    p_check.add_argument("--json", action="store_true", help="Output JSON report")

    p_query = subparsers.add_parser("query", help="Query parquet quant data with optional DuckDB")
    p_query.add_argument("--parquet-root", default="data/quant/parquet", help="Parquet root directory")
    p_query.add_argument("--table", default="daily_bar", help="Table name for simple query mode")
    p_query.add_argument("--market", default=None, help="Optional market filter for simple query mode")
    p_query.add_argument("--limit", type=int, default=5, help="Row limit for simple query mode")
    p_query.add_argument("--sql", default=None, help="DuckDB SQL to execute against parquet tables")
    p_query.add_argument("--tables", default=None, help="Comma-separated table names used by --sql")
    p_query.add_argument("--universe", action="store_true", help="Build a SQL-driven universe from dim_security")
    p_query.add_argument("--universe-name", default="sample_a", help="Universe name for --universe")
    p_query.add_argument("--min-total-mv", type=float, default=None, help="Minimum total_mv for --universe")

    p_qlib = subparsers.add_parser("qlib-convert", help="Convert parquet data to optional Qlib staging artifacts")
    p_qlib.add_argument("--parquet-root", default="data/quant/parquet", help="Parquet root directory")
    p_qlib.add_argument("--output-dir", default="data/quant/qlib_data", help="Qlib output directory")
    p_qlib.add_argument("--market", default="cn", choices=market_codes(), help="Market to convert")
    p_qlib.add_argument("--disable-qlib", action="store_true", help="Write an audited Qlib skip marker")
    return parser


def _load_fixture_tables(fixture_dir: str | Path, market: str) -> dict[str, object]:
    provider = FixtureDataProvider(fixture_dir=fixture_dir, verify_hash=True)
    return provider.read_all(market=market)


def _write_data_version(tables: dict[str, object], source: str, output_dir: Path) -> Path:
    daily_bar = tables["daily_bar"]
    payload = {
        "update_time": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "market": str(daily_bar["market"].dropna().iloc[0]) if "market" in daily_bar.columns else "unknown",
        "base_currency": get_market_config(str(daily_bar["market"].dropna().iloc[0])).currency
        if "market" in daily_bar.columns and not daily_bar["market"].dropna().empty
        else "unknown",
        "benchmark": get_market_config(str(daily_bar["market"].dropna().iloc[0])).benchmark
        if "market" in daily_bar.columns and not daily_bar["market"].dropna().empty
        else "unknown",
        "start_date": str(daily_bar["date"].min()),
        "end_date": str(daily_bar["date"].max()),
        "row_count": {name: int(len(df)) for name, df in tables.items()},
        "hash": {name: dataframe_hash(df) for name, df in tables.items()},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "data_version.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def update_fixture(fixture_dir: str | Path, output_dir: str | Path, market: str = "cn") -> int:
    market = normalize_market(market)
    tables = _load_fixture_tables(fixture_dir, market)
    output_root = Path(output_dir)
    parquet_root = output_root / "parquet"
    for table_name, df in tables.items():
        write_parquet(df, table_name, root=parquet_root)
    version_path = _write_data_version(tables, "fixture", output_root)
    print(f"Updated fixture quant data ({market}): {version_path}")
    for table_name, df in tables.items():
        print(f"- {table_name}: {len(df)} rows")
    return 0


def check_fixture(fixture_dir: str | Path, market: str = "cn", output_json: bool = False) -> int:
    market = normalize_market(market)
    provider = FixtureDataProvider(fixture_dir=fixture_dir, verify_hash=True)
    fixture_root = Path(fixture_dir)
    market_fixture_dir = fixture_root / market if (fixture_root / market).exists() else fixture_root
    report = run_quality_checks(
        daily_bar=provider.get_daily_bar(market=market),
        daily_basic=provider.get_daily_basic(market=market),
        calendar=provider.get_calendar(market=market),
        universe=provider.get_universe(market=market),
        fixture_dir=market_fixture_dir,
    )
    if output_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report.to_text())
    return 0 if report.passed else 1


def _print_query_result(result) -> None:
    print(json.dumps(result.to_metadata(), ensure_ascii=False, sort_keys=True))
    if not result.frame.empty:
        print(result.frame.to_json(orient="records", force_ascii=False))


def run_query(args: argparse.Namespace) -> int:
    filters = {"market": args.market} if args.market else None
    if args.universe:
        result = build_universe(
            root=args.parquet_root,
            market=args.market or "cn",
            universe=args.universe_name,
            min_total_mv=args.min_total_mv,
        )
    elif args.sql:
        table_names = [name.strip() for name in (args.tables or args.table).split(",") if name.strip()]
        result = query_sql(args.sql, table_names=table_names, root=args.parquet_root)
    else:
        result = query_table(
            args.table,
            root=args.parquet_root,
            filters=filters,
            order_by=["date", "symbol"] if args.table in {"daily_bar", "daily_basic"} else None,
            limit=args.limit,
        )
    _print_query_result(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "update":
        if args.market == "all":
            return max(update_fixture(args.fixture_dir, Path(args.output_dir) / market, market) for market in market_codes())
        return update_fixture(args.fixture_dir, args.output_dir, args.market)
    if args.command == "check":
        if args.market == "all":
            return max(check_fixture(args.fixture_dir, market, args.json) for market in market_codes())
        return check_fixture(args.fixture_dir, args.market, args.json)
    if args.command == "query":
        return run_query(args)
    if args.command == "qlib-convert":
        result = convert_parquet_to_qlib(
            parquet_root=args.parquet_root,
            output_dir=args.output_dir,
            market=args.market,
            enabled=not args.disable_qlib,
        )
        print(json.dumps(result.to_metadata(), ensure_ascii=False, sort_keys=True))
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
