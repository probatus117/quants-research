"""Data quality checks for Phase 1 quant fixtures and parquet output."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class QualityIssue:
    check: str
    severity: str
    message: str
    row_count: int = 0


@dataclass
class QualityReport:
    issues: list[QualityIssue] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(self, check: str, severity: str, message: str, row_count: int = 0) -> None:
        self.issues.append(QualityIssue(check, severity, message, row_count))

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "stats": self.stats,
            "issues": [issue.__dict__ for issue in self.issues],
        }

    def to_text(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"Quant data quality report: {status}"]
        for key, value in self.stats.items():
            lines.append(f"- {key}: {value}")
        if not self.issues:
            lines.append("- issues: none")
        else:
            lines.append("- issues:")
            for issue in self.issues:
                suffix = f" ({issue.row_count} rows)" if issue.row_count else ""
                lines.append(f"  [{issue.severity}] {issue.check}: {issue.message}{suffix}")
        return "\n".join(lines)


def dataframe_hash(df: pd.DataFrame) -> str:
    """Return a stable content hash for a DataFrame in its current column order."""
    normalized = df.copy()
    for column in normalized.columns:
        if pd.api.types.is_bool_dtype(normalized[column]):
            normalized[column] = normalized[column].astype(bool)
    payload = normalized.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_expected_hashes(fixture_dir: str | Path) -> dict[str, str]:
    path = Path(fixture_dir) / "sample_hashes.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_quality_checks(
    daily_bar: pd.DataFrame,
    daily_basic: pd.DataFrame,
    calendar: pd.DataFrame,
    universe: pd.DataFrame,
    fixture_dir: str | Path | None = None,
    max_consecutive_missing_days: int = 5,
    max_adj_close_jump: float = 0.35,
) -> QualityReport:
    """Run all Phase 1 data quality checks and return a readable report."""
    report = QualityReport()
    report.stats.update(
        {
            "daily_bar_rows": len(daily_bar),
            "daily_basic_rows": len(daily_basic),
            "calendar_rows": len(calendar),
            "universe_size": int(universe["symbol"].nunique()),
            "markets": sorted(daily_bar["market"].dropna().unique().tolist()) if "market" in daily_bar.columns else [],
            "start_date": str(daily_bar["date"].min()),
            "end_date": str(daily_bar["date"].max()),
            "daily_bar_hash": dataframe_hash(daily_bar),
            "daily_basic_hash": dataframe_hash(daily_basic),
        }
    )

    _check_ohlc(report, daily_bar)
    _check_non_negative(report, daily_bar, ["volume", "amount"], "daily_bar_non_negative")
    _check_non_negative(
        report,
        daily_basic,
        ["total_mv", "circ_mv", "total_share", "float_share", "dividend_yield", "turnover_rate"],
        "daily_basic_non_negative",
    )
    _check_dates_are_open(report, daily_bar, calendar)
    _check_consecutive_missing_days(report, daily_bar, calendar, max_consecutive_missing_days)
    _check_adj_close_jump(report, daily_bar, max_adj_close_jump)
    _check_universe_size(report, universe)
    if fixture_dir is not None:
        _check_fixture_hash_manifest(report, Path(fixture_dir))
    return report


def _check_ohlc(report: QualityReport, daily_bar: pd.DataFrame) -> None:
    bad = daily_bar[
        (daily_bar[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1)
        | (daily_bar["high"] < daily_bar[["open", "close", "low"]].max(axis=1))
        | (daily_bar["low"] > daily_bar[["open", "close", "high"]].min(axis=1))
    ]
    if not bad.empty:
        report.add("ohlc_legal", "error", "OHLC/adj_close boundaries are invalid", len(bad))


def _check_non_negative(report: QualityReport, df: pd.DataFrame, columns: list[str], check: str) -> None:
    bad_count = int((df[columns] < 0).any(axis=1).sum())
    if bad_count:
        report.add(check, "error", f"Negative values found in {columns}", bad_count)


def _check_dates_are_open(report: QualityReport, daily_bar: pd.DataFrame, calendar: pd.DataFrame) -> None:
    if "market" in daily_bar.columns and "market" in calendar.columns:
        open_keys = set(calendar.loc[calendar["is_open"], ["market", "date"]].itertuples(index=False, name=None))
        keys = list(daily_bar[["market", "date"]].itertuples(index=False, name=None))
        bad = daily_bar[[key not in open_keys for key in keys]]
    else:
        open_dates = set(calendar.loc[calendar["is_open"], "date"])
        bad = daily_bar[~daily_bar["date"].isin(open_dates)]
    if not bad.empty:
        report.add("date_trade_calendar", "error", "daily_bar contains non-open calendar dates", len(bad))


def _check_consecutive_missing_days(
    report: QualityReport,
    daily_bar: pd.DataFrame,
    calendar: pd.DataFrame,
    max_consecutive_missing_days: int,
) -> None:
    markets = daily_bar["market"].dropna().unique().tolist() if "market" in daily_bar.columns else [None]
    bad_symbols = 0
    open_index_size = 0
    expected_total = 0
    for market in markets:
        market_calendar = calendar if market is None else calendar[calendar["market"] == market]
        market_bar = daily_bar if market is None else daily_bar[daily_bar["market"] == market]
        open_dates = market_calendar.loc[market_calendar["is_open"], "date"].tolist()
        open_index_size += len({date: index for index, date in enumerate(open_dates)})
        start = market_bar["date"].min()
        end = market_bar["date"].max()
        expected = [date for date in open_dates if start <= date <= end]
        expected_total += len(expected)
        for symbol, group in market_bar.groupby("symbol"):
            present = set(group["date"])
            run = 0
            max_run = 0
            for date in expected:
                if date in present:
                    run = 0
                else:
                    run += 1
                    max_run = max(max_run, run)
            if max_run > max_consecutive_missing_days:
                bad_symbols += 1
    if bad_symbols:
        report.add(
            "consecutive_missing_days",
            "error",
            f"Symbols missing more than {max_consecutive_missing_days} consecutive open days",
            bad_symbols,
        )
    report.stats["calendar_open_days"] = expected_total
    report.stats["calendar_open_index_size"] = open_index_size


def _check_adj_close_jump(report: QualityReport, daily_bar: pd.DataFrame, max_jump: float) -> None:
    sort_keys = ["market", "symbol", "date"] if "market" in daily_bar.columns else ["symbol", "date"]
    group_keys = ["market", "symbol"] if "market" in daily_bar.columns else ["symbol"]
    ordered = daily_bar.sort_values(sort_keys)
    pct = ordered.groupby(group_keys)["adj_close"].pct_change().abs()
    bad_count = int((pct > max_jump).sum())
    if bad_count:
        report.add("adj_close_jump", "warning", f"adj_close jumps exceed {max_jump:.0%}", bad_count)


def _check_universe_size(report: QualityReport, universe: pd.DataFrame, min_size: int = 50, max_size: int = 100) -> None:
    size = int(universe["symbol"].nunique())
    if size < min_size or size > max_size:
        report.add("universe_size", "error", f"Universe size must be between {min_size} and {max_size}", size)


def _check_fixture_hash_manifest(report: QualityReport, fixture_dir: Path) -> None:
    expected_path = fixture_dir / "sample_hashes.json"
    if not expected_path.exists():
        report.add("fixture_hash", "error", f"Missing hash manifest: {expected_path}")
        return
    expected = load_expected_hashes(fixture_dir)
    for name, expected_hash in expected.items():
        path = fixture_dir / name
        if not path.exists():
            report.add("fixture_hash", "error", f"Missing fixture file: {name}")
            continue
        actual = file_hash(path)
        if actual != expected_hash:
            report.add("fixture_hash", "error", f"Hash mismatch for {name}")
