"""Quant experiment registry CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.experiments.registry import list_experiments  # noqa: E402
from src.quant.reports.markdown_report import generate_compare_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant experiment CLI")
    subparsers = parser.add_subparsers(dest="command")
    p_list = subparsers.add_parser("list", help="List quant experiments")
    p_list.add_argument("--experiments-root", default="data/quant/experiments", help="Experiment registry root")
    p_list.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    p_list.add_argument("--limit", type=int, default=20, help="Maximum number of experiments to show")

    p_compare = subparsers.add_parser("compare", help="Generate a metrics comparison report")
    p_compare.add_argument("experiment_ids", nargs="*", help="Experiment IDs; omit to compare all")
    p_compare.add_argument("--experiments-root", default="data/quant/experiments", help="Experiment registry root")
    p_compare.add_argument("--output", default=None, help="Output Markdown path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "list":
        records = list_experiments(args.experiments_root)[: args.limit]
        if args.json:
            print(json.dumps(records, ensure_ascii=True, indent=2, sort_keys=True))
            return 0
        if not records:
            print("No quant experiments found.")
            return 0
        for item in records:
            print(
                "{experiment_id}\t{status}\t{market}\t{task_type}\t{created_at}".format(
                    experiment_id=item.get("experiment_id", ""),
                    status=item.get("status", ""),
                    market=item.get("market", ""),
                    task_type=item.get("task_type", ""),
                    created_at=item.get("created_at", ""),
                )
            )
        return 0
    if args.command == "compare":
        report_path = generate_compare_report(
            experiment_ids=list(args.experiment_ids),
            experiments_root=args.experiments_root,
            output_path=args.output,
        )
        print(f"Compare report: {report_path}")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
