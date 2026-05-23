"""Factor store persistence, coverage reports, and lightweight charts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from src.quant.data.storage import write_parquet
from src.quant.factors.processing import process_factor_values

FACTOR_VALUE_COLUMNS = (
    "date",
    "market",
    "symbol",
    "factor_name",
    "raw_value",
    "winsorized_value",
    "zscore",
    "percentile",
    "direction",
    "universe",
    "zscore_neutral",
)


def combine_and_process(results: list[pd.DataFrame], exposures: pd.DataFrame | None = None) -> pd.DataFrame:
    """Combine raw factor result frames and add standard processed columns."""
    if not results:
        raise ValueError("No factor results to store")
    raw = pd.concat(results, ignore_index=True)
    if exposures is not None and not exposures.empty:
        keys = ["date", "market", "symbol"] if "market" in raw.columns and "market" in exposures.columns else ["date", "symbol"]
        raw = raw.merge(exposures.drop_duplicates(keys), on=keys, how="left")
    processed = process_factor_values(raw)
    if "market" not in processed.columns:
        processed["market"] = "cn"
    return processed[list(FACTOR_VALUE_COLUMNS)]


def write_factor_values(df: pd.DataFrame, parquet_root: str | Path) -> Path:
    """Write factor_value parquet using the standard quant storage layout."""
    return write_parquet(df, "factor_value", root=parquet_root)


def build_coverage_report(df: pd.DataFrame) -> dict[str, object]:
    """Summarize valid factor coverage by factor and date."""
    rows: list[dict[str, object]] = []
    group_keys = ["factor_name", "market", "date"] if "market" in df.columns else ["factor_name", "date"]
    grouped = df.groupby(group_keys, sort=True)
    for key, group in grouped:
        if len(group_keys) == 3:
            factor_name, market, date = key
        else:
            factor_name, date = key
            market = "unknown"
        universe_total = int(group["symbol"].nunique())
        valid_count = int(group["raw_value"].notna().sum())
        rows.append(
            {
                "factor_name": factor_name,
                "market": market,
                "date": str(date),
                "valid_count": valid_count,
                "universe_total": universe_total,
                "coverage": valid_count / universe_total if universe_total else 0.0,
            }
        )

    summary = (
        pd.DataFrame(rows)
        .groupby(["factor_name", "market"], sort=True)["coverage"]
        .agg(["min", "mean", "max"])
        .reset_index()
        .to_dict(orient="records")
        if rows
        else []
    )
    return {"by_date": rows, "summary": summary}


def write_coverage_report(report: dict[str, object], output_dir: str | Path) -> Path:
    path = Path(output_dir) / "factors" / "coverage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_distribution_charts(df: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    """Write per-factor histogram and coverage time-series charts when matplotlib is available."""
    chart_dir = Path(output_dir) / "factors" / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(chart_dir / ".matplotlib"))
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        marker = chart_dir / "matplotlib_unavailable.txt"
        marker.write_text("matplotlib is not installed; distribution charts were skipped.\n", encoding="utf-8")
        return [marker]

    written: list[Path] = []
    coverage = pd.DataFrame(build_coverage_report(df)["by_date"])
    for factor_name, group in df.groupby("factor_name", sort=True):
        histogram_path = chart_dir / f"{factor_name}_hist.png"
        values = group["raw_value"].dropna()
        plt.figure(figsize=(8, 4))
        plt.hist(values, bins=30)
        plt.title(f"{factor_name} raw value distribution")
        plt.tight_layout()
        plt.savefig(histogram_path)
        plt.close()
        written.append(histogram_path)

        series_path = chart_dir / f"{factor_name}_coverage.png"
        factor_coverage = coverage[coverage["factor_name"] == factor_name].copy()
        factor_coverage["date"] = pd.to_datetime(factor_coverage["date"])
        plt.figure(figsize=(8, 4))
        plt.plot(factor_coverage["date"], factor_coverage["coverage"])
        plt.ylim(0, 1.05)
        plt.title(f"{factor_name} coverage")
        plt.tight_layout()
        plt.savefig(series_path)
        plt.close()
        written.append(series_path)
    return written
