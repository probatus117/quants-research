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
from src.quant.data.quality_check import dataframe_hash, run_quality_checks
from src.quant.data.storage import write_parquet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant data pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_update = subparsers.add_parser("update", help="Update quant data")
    p_update.add_argument("--source", default="fixture", choices=["fixture"], help="Data source name")
    p_update.add_argument("--fixture-dir", default="tests/fixtures/quant", help="Fixture directory")
    p_update.add_argument("--output-dir", default="data/quant", help="Quant output directory")

    p_check = subparsers.add_parser("check", help="Run quant data quality checks")
    p_check.add_argument("--source", default="fixture", choices=["fixture"], help="Data source name")
    p_check.add_argument("--fixture-dir", default="tests/fixtures/quant", help="Fixture directory")
    p_check.add_argument("--json", action="store_true", help="Output JSON report")
    return parser


def _load_fixture_tables(fixture_dir: str | Path) -> dict[str, object]:
    provider = FixtureDataProvider(fixture_dir=fixture_dir, verify_hash=True)
    return provider.read_all()


def _write_data_version(tables: dict[str, object], source: str, output_dir: Path) -> Path:
    daily_bar = tables["daily_bar"]
    payload = {
        "update_time": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "start_date": str(daily_bar["date"].min()),
        "end_date": str(daily_bar["date"].max()),
        "row_count": {name: int(len(df)) for name, df in tables.items()},
        "hash": {name: dataframe_hash(df) for name, df in tables.items()},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "data_version.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def update_fixture(fixture_dir: str | Path, output_dir: str | Path) -> int:
    tables = _load_fixture_tables(fixture_dir)
    output_root = Path(output_dir)
    parquet_root = output_root / "parquet"
    for table_name, df in tables.items():
        write_parquet(df, table_name, root=parquet_root)
    version_path = _write_data_version(tables, "fixture", output_root)
    print(f"Updated fixture quant data: {version_path}")
    for table_name, df in tables.items():
        print(f"- {table_name}: {len(df)} rows")
    return 0


def check_fixture(fixture_dir: str | Path, output_json: bool = False) -> int:
    provider = FixtureDataProvider(fixture_dir=fixture_dir, verify_hash=True)
    report = run_quality_checks(
        daily_bar=provider.get_daily_bar(),
        daily_basic=provider.get_daily_basic(),
        calendar=provider.get_calendar(),
        universe=provider.get_universe(),
        fixture_dir=fixture_dir,
    )
    if output_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report.to_text())
    return 0 if report.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "update":
        return update_fixture(args.fixture_dir, args.output_dir)
    if args.command == "check":
        return check_fixture(args.fixture_dir, args.json)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
