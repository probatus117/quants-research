"""Quant report CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.reports.markdown_report import (  # noqa: E402
    generate_experiment_report,
    sync_report_summary_to_neo4j,
    write_report_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant report CLI")
    subparsers = parser.add_subparsers(dest="command")
    p_generate = subparsers.add_parser("generate", help="Generate a quant experiment report")
    p_generate.add_argument("--experiment-id", required=True, help="Experiment ID in the registry")
    p_generate.add_argument(
        "--report-type",
        required=True,
        choices=["factor_eval_report", "backtest_report"],
        help="Report template to render",
    )
    p_generate.add_argument("--experiments-root", default="data/quant/experiments", help="Experiment registry root")
    p_generate.add_argument("--output", default=None, help="Output report path; defaults to experiment report.md")
    p_generate.add_argument("--history-dir", default="data/history/quant", help="Quant history JSON directory")
    p_generate.add_argument("--no-history", action="store_true", help="Skip writing data/history/quant summary")
    p_generate.add_argument("--sync-neo4j", action="store_true", help="Attempt optional Neo4j sync for the summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "generate":
        report_path = generate_experiment_report(
            experiment_id=args.experiment_id,
            report_type=args.report_type,
            experiments_root=args.experiments_root,
            output_path=args.output,
        )
        print(f"Report: {report_path}")
        if not args.no_history:
            summary_path = write_report_summary(
                experiment_id=args.experiment_id,
                report_type=args.report_type,
                report_path=report_path,
                experiments_root=args.experiments_root,
                history_dir=args.history_dir,
            )
            print(f"History: {summary_path}")
            if args.sync_neo4j:
                sync_result = sync_report_summary_to_neo4j(summary_path)
                print(f"Neo4j: {sync_result['status']} ({sync_result['reason']})")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
