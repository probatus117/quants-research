"""Quant evaluation CLI for single-factor evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.storage import read_parquet
from src.quant.evaluation.alphalens_runner import run_alphalens_evaluation
from src.quant.evaluation.factor_correlation import factor_correlation_matrix
from src.quant.evaluation.ic_decay import calculate_ic_decay
from src.quant.evaluation.exporter import export_evaluation
from src.quant.evaluation.minimal_runner import MinimalEvaluationConfig, run_minimal_evaluation
from src.quant.reports.factor_report import write_factor_report
from src.quant.reports.robustness_report import market_cap_group_summary, write_robustness_report, yearly_factor_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant evaluation CLI")
    subparsers = parser.add_subparsers(dest="command")
    p_run = subparsers.add_parser("run", help="Run factor evaluation")
    p_run.add_argument("--input-dir", default="data/quant", help="Quant data directory")
    p_run.add_argument("--output-dir", default="data/quant/evaluation", help="Evaluation output directory")
    p_run.add_argument("--factor", default="momentum_12_1", help="Factor name to evaluate")
    p_run.add_argument("--universe", default="sample_a", help="Universe label")
    p_run.add_argument("--periods", default="5,20,60", help="Comma-separated forward-return periods")
    p_run.add_argument("--factor-column", default="zscore", help="Factor score column to evaluate")
    p_run.add_argument("--min-coverage", type=float, default=0.80, help="Minimum acceptable coverage")
    p_run.add_argument("--alphalens", action="store_true", help="Also run optional Alphalens tear sheet adapter")
    return parser


def _parse_periods(value: str) -> tuple[int, ...]:
    periods = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not periods or any(period <= 0 for period in periods):
        raise ValueError("periods must be comma-separated positive integers")
    return periods


def run_evaluation(
    input_dir: str | Path = "data/quant",
    output_dir: str | Path = "data/quant/evaluation",
    factor: str = "momentum_12_1",
    universe: str = "sample_a",
    periods: str = "5,20,60",
    factor_column: str = "zscore",
    min_coverage: float = 0.80,
    use_alphalens: bool = False,
) -> dict[str, object]:
    parquet_root = Path(input_dir) / "parquet"
    factor_values = read_parquet("factor_value", root=parquet_root)
    daily_bar = read_parquet("daily_bar", root=parquet_root)
    try:
        dim_security = read_parquet("dim_security", root=parquet_root)
    except FileNotFoundError:
        dim_security = None
    config = MinimalEvaluationConfig(
        factor_name=factor,
        periods=_parse_periods(periods),
        universe=universe,
        factor_column=factor_column,
        min_coverage=min_coverage,
    )
    result = run_minimal_evaluation(factor_values, daily_bar, config)
    evaluation_input = result.evaluation_input
    if dim_security is not None and "market_cap_bucket" in dim_security.columns:
        evaluation_input = evaluation_input.merge(
            dim_security[["market", "symbol", "market_cap_bucket"]].drop_duplicates(),
            on=["market", "symbol"],
            how="left",
        )
    output_root = Path(output_dir) / factor
    paths = export_evaluation(result, output_root)
    report_path = write_factor_report(result.factor_summary, result.coverage, output_root / "report.md")
    ic_decay = calculate_ic_decay(result.evaluation_input, periods=config.periods, factor_column=factor_column)
    ic_decay_path = output_root / "ic_decay.csv"
    ic_decay.to_csv(ic_decay_path, index=False)
    factor_corr = factor_correlation_matrix(factor_values, factor_column=factor_column)
    factor_corr_path = output_root / "factor_correlation.csv"
    factor_corr.to_csv(factor_corr_path, index=False)
    rank_ic_values = [row.get("rank_ic_mean") for row in result.factor_summary["ic_summary"] if row.get("period") == config.periods[0]]
    robustness_paths = write_robustness_report(
        output_root,
        {"rank_ic_mean": float(rank_ic_values[0]) if rank_ic_values else 0.0},
        yearly_summary=yearly_factor_summary(evaluation_input, periods=config.periods, factor_column=factor_column),
        cap_group_summary=market_cap_group_summary(evaluation_input, periods=config.periods, factor_column=factor_column),
    )
    summary_path = output_root / "run_summary.json"
    payload: dict[str, object] = {key: str(path) for key, path in paths.items()}
    payload["report"] = str(report_path)
    payload["ic_decay"] = str(ic_decay_path)
    payload["factor_correlation"] = str(factor_corr_path)
    payload["robustness"] = robustness_paths
    payload["warnings"] = result.coverage["warnings"]
    if use_alphalens:
        alphalens_result = run_alphalens_evaluation(
            factor_values,
            daily_bar,
            config,
            output_dir=output_root / "alphalens",
            enabled=True,
        )
        payload["alphalens"] = alphalens_result.to_metadata()
    summary_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["run_summary"] = str(summary_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        try:
            summary = run_evaluation(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                factor=args.factor,
                universe=args.universe,
                periods=args.periods,
                factor_column=args.factor_column,
                min_coverage=args.min_coverage,
                use_alphalens=args.alphalens,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print(f"Evaluation summary: {summary['factor_summary']}")
        print(f"IC timeseries: {summary['ic_timeseries']}")
        print(f"Quantile returns: {summary['quantile_returns']}")
        print(f"Coverage: {summary['coverage']}")
        if args.alphalens:
            print(f"Alphalens: {summary['alphalens']}")
        print(f"Report: {summary['report']}")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
