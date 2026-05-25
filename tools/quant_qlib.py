"""Qlib native data/model/backtest CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.backtest.qlib_native_runner import load_qlib_native_config, run_qlib_native_workflow
from src.quant.data.market_config import market_codes
from src.quant.data.qlib_bin_writer import convert_parquet_to_qlib_bin
from src.quant.experiments.registry import create_experiment, save_artifact, update_status
from src.quant.reports.markdown_report import generate_experiment_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qlib native quant research CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_convert = subparsers.add_parser("convert", help="Convert parquet data to Qlib native bin_data")
    p_convert.add_argument("--parquet-root", default="data/quant/parquet", help="Parquet root directory")
    p_convert.add_argument("--output-dir", default="data/quant/qlib_bin", help="Qlib bin output root")
    p_convert.add_argument("--market", default="cn", choices=market_codes(), help="Market to convert")
    p_convert.add_argument("--disable-qlib", action="store_true", help="Write an audited skip summary")

    p_run = subparsers.add_parser("run", help="Run Qlib native Alpha158/LightGBM/backtest workflow")
    p_run.add_argument("--parquet-root", default="data/quant/parquet", help="Parquet root directory")
    p_run.add_argument("--qlib-bin-dir", default="data/quant/qlib_bin", help="Qlib bin data root")
    p_run.add_argument("--output-dir", default="data/quant/qlib_native", help="Qlib native output root")
    p_run.add_argument("--market", default="cn", choices=market_codes(), help="Market to run")
    p_run.add_argument("--disable-qlib", action="store_true", help="Write audited skip summaries")
    p_run.add_argument("--skip-convert", action="store_true", help="Do not run parquet-to-bin conversion first")
    p_run.add_argument("--register", action="store_true", help="Register Qlib native artifacts as an experiment and render a report")
    p_run.add_argument("--experiments-root", default="data/quant/experiments", help="Experiment registry root for --register")

    p_compare = subparsers.add_parser("compare", help="Write Qlib/Pandas comparison report")
    p_compare.add_argument("--market", default="cn", choices=market_codes(), help="Market to compare")
    p_compare.add_argument("--mode", required=True, choices=["same-signal", "native-research"], help="Comparison semantics")
    p_compare.add_argument("--output-dir", default="data/quant/qlib_native", help="Comparison output root")
    return parser


def _print_metadata(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _write_comparison_report(market: str, mode: str, output_dir: str | Path) -> Path:
    output = Path(output_dir) / market
    output.mkdir(parents=True, exist_ok=True)
    if mode == "same-signal":
        path = output / "qlib_vs_pandas_same_signal_comparison.md"
        lines = [
            "# Qlib vs Pandas Same-Signal Comparison",
            "",
            "- mode: `same-signal`",
            "- scope: same universe, same signal, same rebalance dates, same cost and same adjusted price policy only.",
            "- interpretation: differences may indicate engine, order, calendar, cost, or rounding drift.",
            "",
            "This report is an engine-difference audit placeholder. Populate metric deltas only when both engines use identical input signals.",
        ]
    else:
        path = output / "qlib_native_research_comparison.md"
        lines = [
            "# Qlib Native Research Comparison",
            "",
            "- mode: `native-research`",
            "- scope: pandas MVP factors/backtest versus Qlib Alpha158 + LightGBM native research.",
            "- interpretation: descriptive only; this is not a same-strategy correctness check.",
            "",
            "Native Qlib research uses a different feature set and model, so performance differences should be treated as research evidence, not pass/fail deltas.",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _read_json_if_exists(path: str | Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text(encoding="utf-8"))


def _data_version_from_conversion(conversion) -> dict[str, object]:
    summary = _read_json_if_exists(conversion.artifacts.get("summary") if conversion is not None else None)
    if summary and isinstance(summary.get("data_version"), dict):
        return dict(summary["data_version"])  # type: ignore[arg-type]
    return {
        "data_version": "unknown",
        "source": "qlib_native",
        "universe": "unknown",
        "start_date": "unknown",
        "end_date": "unknown",
    }


def _register_native_experiment(
    *,
    market: str,
    config,
    result,
    conversion,
    output_dir: str | Path,
    experiments_root: str | Path,
) -> dict[str, str]:
    same_signal_report = _write_comparison_report(market, "same-signal", output_dir)
    native_research_report = _write_comparison_report(market, "native-research", output_dir)
    experiment_config = {
        "qlib_native": {
            "market": market,
            "provider_uri": config.resolved_provider_uri(),
            "dataset": config.dataset_config,
            "model": config.model_config,
            "backtest": config.backtest_config,
        }
    }
    record = create_experiment(
        experiment_config,
        _data_version_from_conversion(conversion),
        market,
        "qlib-native",
        root=experiments_root,
    )
    experiment_id = str(record["experiment_id"])
    save_artifact(experiment_id, "metrics.json", result.metrics, root=experiments_root)
    artifact_candidates = [
        result.artifacts.get("summary"),
        result.artifacts.get("predictions"),
        result.artifacts.get("portfolio_metrics"),
        result.artifacts.get("portfolio_value"),
        conversion.artifacts.get("summary") if conversion is not None else None,
        same_signal_report,
        native_research_report,
    ]
    for artifact_path in artifact_candidates:
        if artifact_path and Path(artifact_path).exists():
            save_artifact(experiment_id, Path(artifact_path).name, Path(artifact_path), root=experiments_root)
    update_status(experiment_id, "success", root=experiments_root)
    report_path = generate_experiment_report(experiment_id, "backtest_report", experiments_root=experiments_root)
    return {
        "experiment_id": experiment_id,
        "experiment_dir": str(Path(experiments_root) / experiment_id),
        "report": str(report_path),
        "same_signal_comparison": str(same_signal_report),
        "native_research_comparison": str(native_research_report),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "convert":
        result = convert_parquet_to_qlib_bin(
            parquet_root=args.parquet_root,
            output_dir=args.output_dir,
            market=args.market,
            enabled=not args.disable_qlib,
        )
        _print_metadata(result.to_metadata())
        return 0

    if args.command == "run":
        conversion = None
        if not args.skip_convert:
            conversion = convert_parquet_to_qlib_bin(
                parquet_root=args.parquet_root,
                output_dir=args.qlib_bin_dir,
                market=args.market,
                enabled=not args.disable_qlib,
            )
        config = load_qlib_native_config(market=args.market, qlib_bin_dir=args.qlib_bin_dir)
        result = run_qlib_native_workflow(
            config,
            output_dir=Path(args.output_dir) / args.market,
            enabled=not args.disable_qlib,
        )
        payload = result.to_metadata()
        if conversion is not None:
            payload["conversion"] = conversion.to_metadata()
        if args.register:
            payload["registry"] = _register_native_experiment(
                market=args.market,
                config=config,
                result=result,
                conversion=conversion,
                output_dir=args.output_dir,
                experiments_root=args.experiments_root,
            )
        _print_metadata(payload)
        return 0

    if args.command == "compare":
        path = _write_comparison_report(args.market, args.mode, args.output_dir)
        _print_metadata({"market": args.market, "mode": args.mode, "report": str(path)})
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
