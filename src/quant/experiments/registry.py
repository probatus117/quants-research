"""Experiment registry for quant research artifacts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.quant.experiments.config_hash import calculate_config_hash

DEFAULT_EXPERIMENT_ROOT = Path("data/quant/experiments")
VALID_STATUSES = {"running", "success", "failed"}
TERMINAL_STATUSES = {"success", "failed"}
EXPERIMENT_ID_PATTERN = re.compile(r"^EXP_\d{8}_\d{6}_[A-Za-z0-9-]+_[A-Za-z0-9-]+_[0-9a-f]{10}$")


def _utc_now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9-]+", "-", value.strip())
    token = re.sub(r"-+", "-", token).strip("-")
    if not token:
        raise ValueError("market and task_type must contain at least one alphanumeric character")
    return token


def _experiment_id(now: datetime, market: str, task_type: str, short_hash: str) -> str:
    return f"EXP_{now:%Y%m%d}_{now:%H%M%S}_{_safe_token(market)}_{_safe_token(task_type)}_{short_hash}"


def _metadata_path(experiment_dir: Path) -> Path:
    return experiment_dir / "metadata.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=True), encoding="utf-8")


def _read_metadata(experiment_dir: Path) -> dict[str, Any]:
    path = _metadata_path(experiment_dir)
    if not path.exists():
        raise FileNotFoundError(f"Experiment metadata not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_metadata(experiment_dir: Path, metadata: dict[str, Any]) -> None:
    metadata["updated_at"] = _utc_now().isoformat()
    _write_json(_metadata_path(experiment_dir), metadata)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def create_experiment(
    config: dict[str, Any],
    data_version: dict[str, Any],
    market: str,
    task_type: str,
    root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a running experiment directory with required baseline artifacts."""
    experiments_root = Path(root)
    experiments_root.mkdir(parents=True, exist_ok=True)
    config_hash = calculate_config_hash(config, data_version)
    short_hash = config_hash[:10]
    timestamp = (now or _utc_now()).replace(microsecond=0)

    for offset in range(0, 86_400):
        candidate_time = timestamp + timedelta(seconds=offset)
        experiment_id = _experiment_id(candidate_time, market, task_type, short_hash)
        experiment_dir = experiments_root / experiment_id
        if not experiment_dir.exists():
            break
    else:
        raise RuntimeError("Unable to allocate a unique experiment_id")

    charts_dir = experiment_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=False)
    _write_yaml(experiment_dir / "config.yaml", config)
    _write_json(experiment_dir / "data_version.json", data_version)
    _write_json(experiment_dir / "metrics.json", {})
    (experiment_dir / "report.md").write_text("", encoding="utf-8")

    created_at = candidate_time.isoformat()
    metadata: dict[str, Any] = {
        "experiment_id": experiment_id,
        "status": "running",
        "market": _safe_token(market),
        "task_type": _safe_token(task_type),
        "config_hash": config_hash,
        "short_hash": short_hash,
        "created_at": created_at,
        "updated_at": created_at,
        "experiment_dir": str(experiment_dir),
        "artifacts": {
            "config": "config.yaml",
            "data_version": "data_version.json",
            "metrics": "metrics.json",
            "charts": "charts",
            "report": "report.md",
        },
    }
    _write_json(_metadata_path(experiment_dir), metadata)
    return metadata


def get_experiment(experiment_id: str, root: str | Path = DEFAULT_EXPERIMENT_ROOT) -> dict[str, Any]:
    """Return metadata for one experiment."""
    return _read_metadata(Path(root) / experiment_id)


def list_experiments(root: str | Path = DEFAULT_EXPERIMENT_ROOT) -> list[dict[str, Any]]:
    """List registered experiments, newest first."""
    experiments_root = Path(root)
    if not experiments_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in experiments_root.iterdir():
        if path.is_dir() and _metadata_path(path).exists():
            records.append(_read_metadata(path))
    return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)


def update_status(
    experiment_id: str,
    status: str,
    root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    error: str | None = None,
) -> dict[str, Any]:
    """Move an experiment from running to success or failed."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid experiment status: {status}")
    experiment_dir = Path(root) / experiment_id
    metadata = _read_metadata(experiment_dir)
    current = str(metadata.get("status"))
    if current == status:
        return metadata
    if current in TERMINAL_STATUSES and status != current:
        raise ValueError(f"Cannot transition terminal experiment {experiment_id} from {current} to {status}")
    if current != "running" and status in TERMINAL_STATUSES:
        raise ValueError(f"Cannot transition experiment {experiment_id} from {current} to {status}")

    metadata["status"] = status
    if error:
        metadata["error"] = error
    _write_metadata(experiment_dir, metadata)
    return metadata


def save_artifact(
    experiment_id: str,
    name: str,
    artifact: Any,
    root: str | Path = DEFAULT_EXPERIMENT_ROOT,
) -> Path:
    """Save or copy an artifact into an experiment directory and update metadata."""
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Artifact name must be a relative path inside the experiment directory")
    experiment_dir = Path(root) / experiment_id
    metadata = _read_metadata(experiment_dir)
    output_path = experiment_dir / name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(artifact, Path):
        if artifact.is_dir():
            if output_path.exists():
                shutil.rmtree(output_path)
            shutil.copytree(artifact, output_path)
        else:
            shutil.copy2(artifact, output_path)
    elif isinstance(artifact, bytes):
        output_path.write_bytes(artifact)
    elif isinstance(artifact, str):
        output_path.write_text(artifact, encoding="utf-8")
    elif isinstance(artifact, (dict, list)):
        _write_json(output_path, artifact)
    else:
        raise TypeError(f"Unsupported artifact type: {type(artifact).__name__}")

    key = output_path.stem if output_path.name != "report.md" else "report"
    if output_path.name == "metrics.json":
        key = "metrics"
    metadata.setdefault("artifacts", {})[key] = _relative(output_path, experiment_dir)
    _write_metadata(experiment_dir, metadata)
    return output_path
