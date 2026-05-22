"""Quant factor CLI for factor computation and persistence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.storage import read_parquet
from src.quant.factors import FactorConfig, LowVolatility60DFactor, Momentum121Factor, ValueBPFactor
from src.quant.factors.store import (
    build_coverage_report,
    combine_and_process,
    write_coverage_report,
    write_distribution_charts,
    write_factor_values,
)

FACTOR_REGISTRY = {
    "value_bp": (ValueBPFactor, "daily_basic"),
    "momentum_12_1": (Momentum121Factor, "daily_bar"),
    "lowvol_60d": (LowVolatility60DFactor, "daily_bar"),
}


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
    p_compute.add_argument("--no-charts", action="store_true", help="Skip distribution chart generation")
    return parser


def _parse_factor_names(value: str) -> list[str]:
    if value == "all":
        return list(FACTOR_REGISTRY)
    names = [name.strip() for name in value.split(",") if name.strip()]
    unknown = [name for name in names if name not in FACTOR_REGISTRY]
    if unknown:
        raise ValueError(f"Unknown factors: {', '.join(unknown)}")
    return names


def compute_factors(
    input_dir: str | Path = "data/quant",
    output_dir: str | Path = "data/quant",
    factors: str = "value_bp,momentum_12_1,lowvol_60d",
    universe: str = "sample_a",
    write_charts: bool = True,
) -> dict[str, object]:
    factor_names = _parse_factor_names(factors)
    input_root = Path(input_dir) / "parquet"
    output_root = Path(output_dir)
    table_cache = {
        "daily_basic": read_parquet("daily_basic", root=input_root),
        "daily_bar": read_parquet("daily_bar", root=input_root),
    }

    raw_results = []
    row_counts: dict[str, int] = {}
    for factor_name in factor_names:
        factor_cls, table_name = FACTOR_REGISTRY[factor_name]
        default_factor = factor_cls()
        factor = factor_cls(
            FactorConfig(
                name=default_factor.factor_name,
                direction=default_factor.direction,
                universe=universe,
            )
        )
        result = factor.compute(table_cache[table_name])
        raw_results.append(result.values)
        row_counts[factor_name] = int(len(result.values))

    factor_values = combine_and_process(raw_results)
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
