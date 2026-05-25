"""Optional Qlib compatibility data converter for quant parquet datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.quant.data.storage import DEFAULT_PARQUET_ROOT, read_parquet

try:  # pragma: no cover - environment-specific.
    import qlib

    HAS_QLIB = True
    QLIB_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    qlib = None
    HAS_QLIB = False
    QLIB_IMPORT_ERROR = exc


QLIB_SKIP_REASON = "pyqlib is not installed; qlib bin_data conversion skipped"


@dataclass(frozen=True)
class QlibCapability:
    """Runtime availability for the optional Qlib integration."""

    available: bool
    skip_reason: str | None = None


@dataclass(frozen=True)
class QlibConversionResult:
    """Audit payload for parquet-to-Qlib conversion."""

    available: bool
    fallback_used: bool
    skip_reason: str | None
    artifacts: dict[str, str]
    adapter: str = "qlib_converter"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "available": self.available,
            "fallback_used": self.fallback_used,
            "skip_reason": self.skip_reason,
            "artifacts": self.artifacts,
        }


def check_qlib_capability() -> QlibCapability:
    """Return Qlib availability without making it a hard dependency."""

    if HAS_QLIB and qlib is not None:
        return QlibCapability(available=True)
    if QLIB_IMPORT_ERROR is not None:
        return QlibCapability(available=False, skip_reason=f"pyqlib import failed: {QLIB_IMPORT_ERROR}; qlib bin_data conversion skipped")
    return QlibCapability(available=False, skip_reason=QLIB_SKIP_REASON)


def convert_parquet_to_qlib(
    parquet_root: str | Path = DEFAULT_PARQUET_ROOT,
    output_dir: str | Path = "data/quant/qlib_data",
    market: str = "cn",
    enabled: bool = True,
) -> QlibConversionResult:
    """Create legacy CSV staging artifacts, or an audited skip marker.

    This compatibility runner is kept for existing callers. Native Qlib
    bin_data conversion lives in ``src.quant.data.qlib_bin_writer``.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "qlib_conversion_summary.json"
    capability = check_qlib_capability()
    if not enabled or not capability.available:
        reason = "qlib disabled by caller; qlib bin_data conversion skipped" if not enabled else capability.skip_reason
        result = QlibConversionResult(
            available=False,
            fallback_used=True,
            skip_reason=reason or QLIB_SKIP_REASON,
            artifacts={"summary": str(summary_path)},
        )
        summary_path.write_text(json.dumps(result.to_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    daily_bar = read_parquet("daily_bar", root=parquet_root)
    if "market" in daily_bar.columns:
        daily_bar = daily_bar[daily_bar["market"] == market].copy()
    staging_dir = output / market / "csv_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    instruments_path = output / market / "instruments.txt"
    calendar_path = output / market / "calendar.txt"
    price_path = staging_dir / "daily_bar.csv"
    daily_bar.sort_values(["symbol", "date"]).to_csv(price_path, index=False)
    symbols = sorted(daily_bar["symbol"].astype(str).unique().tolist())
    dates = sorted(daily_bar["date"].astype(str).unique().tolist())
    instruments_path.write_text("\n".join(symbols) + "\n", encoding="utf-8")
    calendar_path.write_text("\n".join(dates) + "\n", encoding="utf-8")
    result = QlibConversionResult(
        available=True,
        fallback_used=False,
        skip_reason=None,
        artifacts={
            "csv_staging": str(staging_dir),
            "daily_bar_csv": str(price_path),
            "instruments": str(instruments_path),
            "calendar": str(calendar_path),
            "summary": str(summary_path),
        },
    )
    payload = {
        **result.to_metadata(),
        "runner_type": "compatibility converter",
        "deprecation": "Use convert_parquet_to_qlib_bin() for Qlib native bin_data.",
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
