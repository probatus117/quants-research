"""Quant experiment CLI stub for Phase 0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant experiment CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run quant experiment")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    print("Phase 0 stub: quant_experiment command wiring only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
