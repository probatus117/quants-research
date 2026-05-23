"""Quant factor CLI for factor computation and persistence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
import pandas as pd

from src.quant.data.market_config import normalize_market
from src.quant.data.storage import QuantStorageError, read_parquet
from src.quant.factors.registry import available_factor_names, load_factor_specs
from src.quant.factors.store import (
    build_coverage_report,
    combine_and_process,
    write_coverage_report,
    write_distribution_charts,
    write_factor_values,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant factor pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")
    p_compute = subparsers.add_parser("compute", help="Compute quant factors")
    p_compute.add_argument("--input-dir", default="data/quant", help="Quant data directory")
    p_compute.add_argument("--output-dir", default="data/quant", help="Quant output directory")
    p_compute.add_argument(
        "--factors",
        default="value_bp,momentum_12_1,lowvol_60d",
        help="Comma-separated factor names or 'all'",
    )
    p_compute.add_argument("--universe", default="sample_a", help="Universe label stored with factor values")
    p_compute.add_argument("--market", default="cn", help="Market code: cn/us/jp")
    p_compute.add_argument("--config", default="config/quant_factors.yaml", help="Factor YAML config")
    p_compute.add_argument("--no-charts", action="store_true", help="Skip distribution chart generation")
    return parser


def _parse_factor_names(value: str) -> list[str]:
    if value == "all":
        return available_factor_names()
    names = [name.strip() for name in value.split(",") if name.strip()]
    unknown = [name for name in names if name not in available_factor_names()]
    if unknown:
        raise ValueError(f"Unknown factors: {', '.join(unknown)}")
    return names


def _build_exposures(input_root: Path) -> pd.DataFrame | None:
    try:
        daily_basic = read_parquet("daily_basic", root=input_root)
        universe = read_parquet("dim_security", root=input_root)
    except QuantStorageError:
        return None
    keys = ["market", "symbol"] if "market" in universe.columns else ["symbol"]
    exposure = daily_basic.copy()
    exposure["log_market_cap"] = np.log(pd.to_numeric(exposure["total_mv"], errors="coerce").where(lambda s: s > 0))
    exposure = exposure.merge(universe[[*keys, "industry"]].drop_duplicates(keys), on=keys, how="left")
    date_keys = ["date", *keys]
    return exposure[[*date_keys, "industry", "log_market_cap"]]


def compute_factors(
    input_dir: str | Path = "data/quant",
    output_dir: str | Path = "data/quant",
    factors: str = "value_bp,momentum_12_1,lowvol_60d",
    universe: str = "sample_a",
    market: str = "cn",
    config_path: str | Path = "config/quant_factors.yaml",
    write_charts: bool = True,
) -> dict[str, object]:
    market = normalize_market(market)
    factor_names = _parse_factor_names(factors)
    specs = load_factor_specs(config_path, market=market, names=factor_names)
    input_root = Path(input_dir) / "parquet"
    output_root = Path(output_dir)
    table_cache = {
        "daily_basic": read_parquet("daily_basic", root=input_root),
        "daily_bar": read_parquet("daily_bar", root=input_root),
    }
    for table_name, table in table_cache.items():
        if "market" in table.columns:
            table_cache[table_name] = table[table["market"] == market].copy()

    raw_results = []
    row_counts: dict[str, int] = {}
    for spec in specs:
        factor = spec.build(universe=universe)
        result = factor.compute(table_cache[spec.source_table])
        raw_results.append(result.values)
        row_counts[spec.name] = int(len(result.values))

    exposures = _build_exposures(input_root)
    if exposures is not None and "market" in exposures.columns:
        exposures = exposures[exposures["market"] == market].copy()
    factor_values = combine_and_process(raw_results, exposures=exposures)
    factor_path = write_factor_values(factor_values, parquet_root=output_root / "parquet")
    coverage_report = build_coverage_report(factor_values)
    coverage_path = write_coverage_report(coverage_report, output_root)
    chart_paths = write_distribution_charts(factor_values, output_root) if write_charts else []

    return {
        "factor_path": str(factor_path),
        "coverage_path": str(coverage_path),
        "chart_paths": [str(path) for path in chart_paths],
        "row_counts": row_counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "compute":
        try:
            summary = compute_factors(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                factors=args.factors,
                universe=args.universe,
                market=args.market,
                config_path=args.config,
                write_charts=not args.no_charts,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print(f"Computed quant factors: {summary['factor_path']}")
        print(f"Coverage report: {summary['coverage_path']}")
        for factor_name, row_count in summary["row_counts"].items():
            print(f"- {factor_name}: {row_count} rows")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
