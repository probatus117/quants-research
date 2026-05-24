"""Phase 5 Markdown reports for quant experiments."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
import pandas as pd

from src.quant.experiments.registry import DEFAULT_EXPERIMENT_ROOT, get_experiment, list_experiments

REPORT_TYPES = {"factor_eval_report", "backtest_report", "experiment_compare_report"}
SECTION_TITLES = [
    "实验摘要",
    "数据与股票池",
    "因子/策略定义",
    "核心指标",
    "图表与 artifact",
    "稳健性与风险提示",
    "结论边界与下一步",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required JSON artifact not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required YAML artifact not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML artifact must be a mapping: {path}")
    return payload


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (dict, list)):
        return f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"
    return str(value)


def _metrics_table(metrics: dict[str, Any]) -> list[str]:
    if not metrics:
        return ["| metric | value |", "|---|---:|", "| no_metrics | n/a |"]
    lines = ["| metric | value |", "|---|---:|"]
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, (int, float, str, bool)) or value is None:
            lines.append(f"| `{key}` | {_format_value(value)} |")
    return lines


def _artifact_lines(experiment_dir: Path, metadata: dict[str, Any]) -> list[str]:
    artifacts = metadata.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return ["- No artifact metadata found."]
    lines = []
    for name, rel_path in sorted(artifacts.items()):
        path = experiment_dir / str(rel_path)
        state = "ok" if path.exists() else "missing"
        lines.append(f"- `{name}`: `{rel_path}` ({state})")
    return lines or ["- No artifacts registered."]


def _config_brief(config: dict[str, Any], report_type: str) -> list[str]:
    if report_type == "backtest_report":
        backtest = config.get("backtest", config)
        return [
            f"- signal: `{backtest.get('signal', backtest.get('signal_name', 'unknown'))}`",
            f"- frequency: `{backtest.get('frequency', 'unknown')}`",
            f"- top_n: `{backtest.get('top_n', 'unknown')}`",
            f"- weight: `{backtest.get('weight', 'equal')}`",
        ]
    return [
        f"- factor: `{config.get('factor', config.get('factor_name', 'unknown'))}`",
        f"- periods: `{config.get('periods', 'unknown')}`",
        f"- factor_column: `{config.get('factor_column', 'unknown')}`",
    ]


def _robustness_lines(experiment_dir: Path) -> list[str]:
    """Render dynamic robustness hints from optional Phase 7 artifacts."""
    lines: list[str] = []
    robustness_path = experiment_dir / "robustness_report.json"
    walk_forward_path = experiment_dir / "walk_forward_metrics.csv"
    ic_decay_path = experiment_dir / "ic_decay.csv"
    if robustness_path.exists():
        payload = _read_json(robustness_path)
        if "label" in payload:
            lines.append(f"- robustness_label: `{payload['label']}`")
        for key in sorted(payload):
            lines.append(f"- robustness.{key}: `{_format_value(payload[key])}`")
    if walk_forward_path.exists():
        frame = pd.read_csv(walk_forward_path)
        if not frame.empty:
            lines.append(f"- walk_forward_windows: `{len(frame)}`")
            if "sharpe" in frame.columns:
                lines.append(f"- walk_forward_sharpe_min: `{frame['sharpe'].min():.6g}`")
            if "max_drawdown" in frame.columns:
                lines.append(f"- walk_forward_max_drawdown_min: `{frame['max_drawdown'].min():.6g}`")
    if ic_decay_path.exists():
        frame = pd.read_csv(ic_decay_path)
        if not frame.empty:
            lines.append(f"- ic_decay_periods: `{sorted(frame['period'].dropna().astype(int).unique().tolist())}`")
            metric = "rank_ic_mean" if "rank_ic_mean" in frame.columns else "ic_mean"
            if metric in frame.columns:
                lines.append(f"- ic_decay_{metric}_min: `{frame[metric].min():.6g}`")
    return lines or [
        "- No Phase 7 robustness artifacts found; treat the result as a single-run research artifact.",
        "- Review coverage, sample size, turnover, transaction cost, market, currency, and benchmark assumptions before reuse.",
    ]


def render_experiment_report(
    report_type: str,
    metadata: dict[str, Any],
    config: dict[str, Any],
    data_version: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    """Render a 7-section Markdown report from experiment artifacts."""
    if report_type not in {"factor_eval_report", "backtest_report"}:
        raise ValueError(f"Unsupported single-experiment report type: {report_type}")
    experiment_dir = Path(str(metadata["experiment_dir"]))
    title = "Factor Evaluation Report" if report_type == "factor_eval_report" else "Backtest Report"
    lines = [
        f"# Quant {title}: {metadata['experiment_id']}",
        "",
        f"## {SECTION_TITLES[0]}",
        f"- experiment_id: `{metadata['experiment_id']}`",
        f"- status: `{metadata.get('status', 'unknown')}`",
        f"- market: `{metadata.get('market', 'unknown')}`",
        f"- task_type: `{metadata.get('task_type', 'unknown')}`",
        f"- config_hash: `{metadata.get('config_hash', 'unknown')}`",
        "",
        f"## {SECTION_TITLES[1]}",
        f"- data_version: `{data_version.get('data_version', data_version.get('version', 'unknown'))}`",
        f"- universe: `{data_version.get('universe', config.get('universe', 'unknown'))}`",
        f"- date_range: `{data_version.get('start_date', 'unknown')}` to `{data_version.get('end_date', 'unknown')}`",
        "",
        f"## {SECTION_TITLES[2]}",
        *_config_brief(config, report_type),
        "",
        f"## {SECTION_TITLES[3]}",
        *_metrics_table(metrics),
        "",
        f"## {SECTION_TITLES[4]}",
        *_artifact_lines(experiment_dir, metadata),
        "",
        f"## {SECTION_TITLES[5]}",
        *_robustness_lines(experiment_dir),
        "- Neo4j sync is optional; local artifacts are the source of truth.",
        "",
        f"## {SECTION_TITLES[6]}",
        "- This report provides traceable quant evidence, not buy/sell advice.",
        "- Next step: compare this experiment with adjacent factors or backtest settings before strategy use.",
        "",
    ]
    return "\n".join(lines)


def render_compare_report(experiments: list[dict[str, Any]], metrics_by_id: dict[str, dict[str, Any]]) -> str:
    """Render a 7-section comparison report for registered experiments."""
    metric_names = sorted({key for metrics in metrics_by_id.values() for key, value in metrics.items() if isinstance(value, (int, float, str, bool)) or value is None})
    lines = [
        "# Quant Experiment Compare Report",
        "",
        f"## {SECTION_TITLES[0]}",
        f"- experiments: `{len(experiments)}`",
        "",
        f"## {SECTION_TITLES[1]}",
        "- See each experiment's `data_version.json` artifact for the exact universe and date range.",
        "",
        f"## {SECTION_TITLES[2]}",
        "- This comparison reads only registered experiment metadata and `metrics.json` artifacts.",
        "",
        f"## {SECTION_TITLES[3]}",
    ]
    header = ["experiment_id", "status", *metric_names]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join("---" for _ in header) + "|")
    for item in experiments:
        experiment_id = str(item["experiment_id"])
        metrics = metrics_by_id.get(experiment_id, {})
        row = [experiment_id, str(item.get("status", "unknown")), *[_format_value(metrics.get(name, "n/a")) for name in metric_names]]
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(
        [
            "",
            f"## {SECTION_TITLES[4]}",
            "- Comparison rows link back to each experiment directory and its artifacts.",
            "",
            f"## {SECTION_TITLES[5]}",
            "- Do not compare experiments with different universes, date ranges, or cost assumptions without noting the mismatch.",
            "",
            f"## {SECTION_TITLES[6]}",
            "- Use this comparison as an audit index; inspect individual reports before drawing conclusions.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_experiment_report(
    experiment_id: str,
    report_type: str,
    experiments_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    output_path: str | Path | None = None,
) -> Path:
    """Generate a single-experiment report.md from registry artifacts."""
    if report_type not in {"factor_eval_report", "backtest_report"}:
        raise ValueError(f"Unsupported report type for generate: {report_type}")
    metadata = get_experiment(experiment_id, experiments_root)
    experiment_dir = Path(str(metadata["experiment_dir"]))
    config = _read_yaml(experiment_dir / "config.yaml")
    data_version = _read_json(experiment_dir / "data_version.json")
    metrics = _read_json(experiment_dir / "metrics.json")
    report = render_experiment_report(report_type, metadata, config, data_version, metrics)
    path = Path(output_path) if output_path else experiment_dir / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def generate_compare_report(
    experiment_ids: list[str],
    experiments_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    output_path: str | Path | None = None,
) -> Path:
    """Generate a comparison report for experiment IDs."""
    if not experiment_ids:
        experiments = list_experiments(experiments_root)
    else:
        experiments = [get_experiment(experiment_id, experiments_root) for experiment_id in experiment_ids]
    metrics_by_id: dict[str, dict[str, Any]] = {}
    for item in experiments:
        experiment_dir = Path(str(item["experiment_dir"]))
        metrics_by_id[str(item["experiment_id"])] = _read_json(experiment_dir / "metrics.json")
    report = render_compare_report(experiments, metrics_by_id)
    if output_path is None:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = Path(experiments_root) / f"compare_{stamp}.md"
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def write_report_summary(
    experiment_id: str,
    report_type: str,
    report_path: str | Path,
    experiments_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    history_dir: str | Path = "data/history/quant",
) -> Path:
    """Write a compact history JSON entry for a generated quant report."""
    metadata = get_experiment(experiment_id, experiments_root)
    experiment_dir = Path(str(metadata["experiment_dir"]))
    metrics = _read_json(experiment_dir / "metrics.json")
    now = datetime.utcnow().replace(microsecond=0)
    payload = {
        "category": "quant",
        "date": now.date().isoformat(),
        "timestamp": now.isoformat(),
        "experiment_id": experiment_id,
        "report_type": report_type,
        "market": metadata.get("market"),
        "task_type": metadata.get("task_type"),
        "status": metadata.get("status"),
        "metrics": metrics,
        "report_path": str(report_path),
        "_saved_at": now.isoformat(),
    }
    root = Path(history_dir)
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"{now:%Y-%m-%d}_{experiment_id}.json"
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def sync_report_summary_to_neo4j(summary_path: str | Path) -> dict[str, str]:
    """Optionally sync a quant report summary to Neo4j without blocking report generation."""
    mode = os.environ.get("NEO4J_MODE", "").strip().lower()
    if mode == "off":
        return {"status": "skipped", "reason": "NEO4J_MODE=off"}
    try:
        from src.data.graph_store._common import _get_driver, get_mode, is_available
    except ImportError:
        return {"status": "skipped", "reason": "neo4j graph_store unavailable"}
    try:
        resolved_mode = mode or get_mode()
        if resolved_mode == "off" or not is_available():
            return {"status": "skipped", "reason": "neo4j unavailable"}
        driver = _get_driver()
        if driver is None:
            return {"status": "skipped", "reason": "neo4j driver unavailable"}
        payload = _read_json(Path(summary_path))
        with driver.session() as session:
            session.run(
                """
                MERGE (q:QuantReport {id: $id})
                SET q.experiment_id = $experiment_id,
                    q.report_type = $report_type,
                    q.market = $market,
                    q.task_type = $task_type,
                    q.status = $status,
                    q.timestamp = $timestamp
                """,
                id=f"quant_{payload['experiment_id']}",
                experiment_id=payload["experiment_id"],
                report_type=payload["report_type"],
                market=payload.get("market"),
                task_type=payload.get("task_type"),
                status=payload.get("status"),
                timestamp=payload.get("timestamp"),
            )
        return {"status": "success", "reason": "synced"}
    except Exception as exc:
        return {"status": "skipped", "reason": type(exc).__name__}
