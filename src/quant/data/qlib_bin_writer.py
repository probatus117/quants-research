"""Qlib native bin_data writer for quant parquet datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.quant.data.market_config import normalize_market
from src.quant.data.qlib_converter import QLIB_SKIP_REASON, QlibConversionResult
from src.quant.data.storage import DEFAULT_PARQUET_ROOT, QuantStorageError, read_parquet

QLIB_BIN_FIELDS = ("open", "high", "low", "close", "volume", "vwap", "factor", "change")
PRICE_ADJUSTMENT_POLICY = "write adjusted open/high/low/close/vwap; factor=adj_close/close clipped to [0.01, 100]"


@dataclass(frozen=True)
class QlibDataCapability:
    """Runtime availability for Qlib native data storage."""

    qlib_available: bool
    qlib_data_available: bool
    skip_reason: str | None = None
    import_errors: dict[str, str] | None = None

    @property
    def available(self) -> bool:
        return self.qlib_data_available

    def to_dict(self) -> dict[str, Any]:
        return {
            "qlib_available": self.qlib_available,
            "qlib_data_available": self.qlib_data_available,
            "skip_reason": self.skip_reason,
            "import_errors": self.import_errors or {},
        }


@dataclass(frozen=True)
class QlibProviderInitResult:
    """Resolved Qlib provider init metadata."""

    provider_uri: dict[str, str]
    region: str
    region_mapping: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_uri": self.provider_uri,
            "region": self.region,
            "region_mapping": self.region_mapping,
        }


@dataclass(frozen=True)
class QlibCalendarIndex:
    """Trading calendar and ordinal lookup for Qlib feature writes."""

    calendar: list[str]
    date_to_index: dict[str, int]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return str(value)


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")


def check_qlib_data_capability() -> QlibDataCapability:
    """Check Qlib data layer imports, not just the top-level package."""

    errors: dict[str, str] = {}
    try:
        import qlib  # noqa: F401

        qlib_available = True
    except Exception as exc:  # pragma: no cover - environment-specific.
        errors["qlib"] = f"{type(exc).__name__}: {exc}"
        return QlibDataCapability(
            qlib_available=False,
            qlib_data_available=False,
            skip_reason=f"pyqlib import failed: {exc}; qlib native bin_data conversion skipped",
            import_errors=errors,
        )

    try:
        from qlib.data.storage.file_storage import FileFeatureStorage  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment-specific.
        errors["FileFeatureStorage"] = f"{type(exc).__name__}: {exc}"
    try:
        from qlib.data import D  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment-specific.
        errors["D"] = f"{type(exc).__name__}: {exc}"
    try:
        from qlib import init as qlib_init  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment-specific.
        errors["qlib.init"] = f"{type(exc).__name__}: {exc}"

    if errors:
        return QlibDataCapability(
            qlib_available=qlib_available,
            qlib_data_available=False,
            skip_reason=f"Qlib data layer unavailable: {'; '.join(f'{k}={v}' for k, v in errors.items())}",
            import_errors=errors,
        )
    return QlibDataCapability(qlib_available=True, qlib_data_available=True)


def _qlib_region_for_market(market: str) -> tuple[str, dict[str, str]]:
    normalized = normalize_market(market)
    mapping = {"cn": "cn", "us": "us", "jp": "us"}
    region = mapping[normalized]
    return region, {normalized: region}


def init_qlib_provider(output_market_dir: str | Path, market: str) -> QlibProviderInitResult:
    """Initialize Qlib against a native bin_data directory."""

    region, region_mapping = _qlib_region_for_market(market)
    provider_uri = {"day": str(Path(output_market_dir))}
    import qlib

    qlib.init(
        provider_uri=provider_uri,
        region=region,
        expression_cache=None,
        dataset_cache=None,
        redis_port=-1,
    )
    return QlibProviderInitResult(provider_uri=provider_uri, region=region, region_mapping=region_mapping)


def build_qlib_instrument_name(symbol: str, exchange: str | None, market: str) -> str:
    """Map project symbols to Qlib native instrument names."""

    normalized = normalize_market(market)
    raw_symbol = str(symbol).strip()
    raw_exchange = "" if exchange is None or pd.isna(exchange) else str(exchange).strip().upper()
    if normalized == "cn":
        if raw_exchange not in {"SH", "SZ"}:
            raise ValueError(f"CN instrument {raw_symbol} requires exchange SH/SZ for Qlib prefix; got {exchange!r}")
        return f"{raw_exchange.lower()}{raw_symbol}"
    return raw_symbol


def compute_adj_factor(daily_bar: pd.DataFrame) -> pd.Series:
    """Compute clipped adjustment factors from adj_close and close."""

    required = {"close", "adj_close"}
    missing = sorted(required - set(daily_bar.columns))
    if missing:
        raise ValueError(f"daily_bar missing columns for adjustment factor: {', '.join(missing)}")
    close = pd.to_numeric(daily_bar["close"], errors="coerce")
    adj_close = pd.to_numeric(daily_bar["adj_close"], errors="coerce")
    factor = adj_close.divide(close.where(close != 0))
    factor = factor.replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(lower=0.01, upper=100.0)
    return factor.astype(float)


def normalize_qlib_bar_fields(daily_bar: pd.DataFrame, market: str | None = None) -> pd.DataFrame:
    """Normalize raw project bars into Qlib feature fields."""

    required = {"date", "symbol", "open", "high", "low", "close", "adj_close", "volume"}
    missing = sorted(required - set(daily_bar.columns))
    if missing:
        raise ValueError(f"daily_bar missing columns for Qlib bin conversion: {', '.join(missing)}")

    bars = daily_bar.copy()
    if market is not None and "market" in bars.columns:
        bars = bars[bars["market"].astype(str).str.lower() == normalize_market(market)].copy()
    if bars.empty:
        raise ValueError(f"daily_bar has no rows for market={market!r}")

    inferred_market = str(bars["market"].dropna().iloc[0]) if "market" in bars.columns and not bars["market"].dropna().empty else "cn"
    resolved_market = normalize_market(market or inferred_market)
    bars["date"] = pd.to_datetime(bars["date"]).dt.strftime("%Y-%m-%d")
    bars["factor"] = compute_adj_factor(bars)
    for field in ("open", "high", "low", "close"):
        raw = pd.to_numeric(bars[field], errors="coerce")
        bars[field] = raw * bars["factor"]
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce")

    amount_usable = "amount" in bars.columns and bars["amount"].notna().any() and (bars["volume"].fillna(0) > 0).any()
    if amount_usable:
        amount = pd.to_numeric(bars["amount"], errors="coerce")
        raw_vwap = amount.divide(bars["volume"].where(bars["volume"] > 0))
        adjusted_typical = bars[["high", "low", "close"]].mean(axis=1)
        bars["vwap"] = (raw_vwap * bars["factor"]).replace([np.inf, -np.inf], np.nan).fillna(adjusted_typical)
        vwap_policy = "amount / volume * factor with adjusted typical price fallback"
    else:
        bars["vwap"] = bars[["high", "low", "close"]].mean(axis=1)
        vwap_policy = "adjusted typical price fallback because amount or usable volume is missing"

    if "exchange" not in bars.columns:
        bars["exchange"] = pd.NA
    bars["instrument"] = [
        build_qlib_instrument_name(symbol, exchange, resolved_market)
        for symbol, exchange in zip(bars["symbol"], bars["exchange"], strict=False)
    ]
    bars = bars.sort_values(["instrument", "date"]).reset_index(drop=True)
    bars["change"] = bars.groupby("instrument", sort=False)["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bars.attrs["vwap_policy"] = vwap_policy
    bars.attrs["price_adjustment_policy"] = PRICE_ADJUSTMENT_POLICY
    return bars


def build_calendar_index(
    calendar: pd.DataFrame | None,
    daily_bar: pd.DataFrame,
    market: str | None = None,
) -> QlibCalendarIndex:
    """Build a complete Qlib trading calendar and date ordinal lookup."""

    inferred_market = str(daily_bar["market"].dropna().iloc[0]) if "market" in daily_bar.columns and not daily_bar["market"].dropna().empty else "cn"
    normalized = normalize_market(market or inferred_market)
    if calendar is not None and not calendar.empty and "date" in calendar.columns:
        cal = calendar.copy()
        if "market" in cal.columns:
            cal = cal[cal["market"].astype(str).str.lower() == normalized].copy()
        if "is_open" in cal.columns:
            cal = cal[cal["is_open"].astype(bool)].copy()
        dates = pd.to_datetime(cal["date"]).dt.strftime("%Y-%m-%d").dropna().drop_duplicates().sort_values().tolist()
    else:
        bars = daily_bar.copy()
        if "market" in bars.columns:
            bars = bars[bars["market"].astype(str).str.lower() == normalized].copy()
        dates = pd.to_datetime(bars["date"]).dt.strftime("%Y-%m-%d").dropna().drop_duplicates().sort_values().tolist()
    if not dates:
        raise ValueError(f"No calendar dates available for market={normalized}")
    return QlibCalendarIndex(calendar=dates, date_to_index={date: idx for idx, date in enumerate(dates)})


def write_qlib_text_files(
    calendar: QlibCalendarIndex,
    instruments: pd.DataFrame,
    output_market_dir: str | Path,
    market_or_universe: str,
) -> dict[str, str]:
    """Write Qlib calendars/day.txt and instruments/{market}.txt."""

    output = Path(output_market_dir)
    calendar_path = output / "calendars" / "day.txt"
    instrument_path = output / "instruments" / f"{market_or_universe}.txt"
    calendar_path.parent.mkdir(parents=True, exist_ok=True)
    instrument_path.parent.mkdir(parents=True, exist_ok=True)
    calendar_path.write_text("\n".join(calendar.calendar) + "\n", encoding="utf-8")
    rows = [
        f"{row.instrument}\t{row.start_datetime}\t{row.end_datetime}"
        for row in instruments.sort_values("instrument").itertuples(index=False)
    ]
    instrument_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return {"calendar": str(calendar_path), "instruments": str(instrument_path)}


def _instrument_spans(normalized_bar: pd.DataFrame) -> pd.DataFrame:
    return (
        normalized_bar.groupby("instrument", as_index=False)
        .agg(start_datetime=("date", "min"), end_datetime=("date", "max"))
        .sort_values("instrument")
        .reset_index(drop=True)
    )


def _file_feature_storage_class():
    from qlib.data.storage.file_storage import FileFeatureStorage

    return FileFeatureStorage


def write_qlib_features(
    normalized_bar: pd.DataFrame,
    calendar: QlibCalendarIndex,
    output_market_dir: str | Path,
    fields: tuple[str, ...] = QLIB_BIN_FIELDS,
) -> dict[str, str]:
    """Write feature .bin files for each instrument and field."""

    output = Path(output_market_dir)
    provider_uri = {"day": str(output)}
    storage_cls = _file_feature_storage_class()
    artifacts: dict[str, str] = {}
    full_index = pd.Index(calendar.calendar, name="date")
    for instrument, frame in normalized_bar.groupby("instrument", sort=True):
        feature_dir = output / "features" / str(instrument)
        feature_dir.mkdir(parents=True, exist_ok=True)
        aligned = frame.set_index("date").reindex(full_index)
        first_date = str(frame["date"].min())
        first_calendar_idx = calendar.date_to_index[first_date]
        for field in fields:
            values = pd.to_numeric(aligned[field], errors="coerce").iloc[first_calendar_idx:].astype("float32").to_numpy()
            storage = storage_cls(str(instrument), field, "day", provider_uri=provider_uri)
            storage.write(values, index=first_calendar_idx)
            artifacts[f"{instrument}.{field}"] = str(feature_dir / f"{field}.day.bin")
    return artifacts


def verify_qlib_bin_readback(
    output_market_dir: str | Path,
    market: str,
    normalized_bar: pd.DataFrame,
    calendar: QlibCalendarIndex,
    tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Run a minimal FileFeatureStorage and D.features readback check."""

    if normalized_bar.empty:
        raise ValueError("Cannot verify empty Qlib feature dataset")
    output = Path(output_market_dir)
    provider_uri = {"day": str(output)}
    storage_cls = _file_feature_storage_class()
    first_row = normalized_bar.sort_values(["instrument", "date"]).iloc[0]
    instrument = str(first_row["instrument"])
    field = "close"
    storage = storage_cls(instrument, field, "day", provider_uri=provider_uri)
    series = storage[:]
    idx = calendar.date_to_index[str(first_row["date"])]
    storage_value = float(series.iloc[idx] if hasattr(series, "iloc") else series[idx])
    expected = float(first_row[field])
    if not np.isclose(storage_value, expected, rtol=tolerance, atol=tolerance, equal_nan=True):
        raise ValueError(f"FileFeatureStorage readback mismatch for {instrument}.{field}: got {storage_value}, expected {expected}")

    init_qlib_provider(output, market)
    from qlib.data import D

    features = D.features([instrument], [f"${field}"], start_time=str(first_row["date"]), end_time=str(first_row["date"]), freq="day")
    d_value = float(features.iloc[0, 0])
    if not np.isclose(d_value, expected, rtol=tolerance, atol=tolerance, equal_nan=True):
        raise ValueError(f"D.features readback mismatch for {instrument}.${field}: got {d_value}, expected {expected}")
    return {"instrument": instrument, "field": field, "expected": expected, "file_storage_value": storage_value, "d_features_value": d_value}


def _read_optional_parquet(table_name: str, parquet_root: str | Path) -> pd.DataFrame | None:
    try:
        return read_parquet(table_name, root=parquet_root)
    except QuantStorageError:
        return None


def _read_data_version(parquet_root: str | Path) -> dict[str, Any] | None:
    path = Path(parquet_root).parent / "data_version.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"path": str(path), "parse_error": True}


def convert_parquet_to_qlib_bin(
    parquet_root: str | Path = DEFAULT_PARQUET_ROOT,
    output_dir: str | Path = "data/quant/qlib_bin",
    market: str = "cn",
    enabled: bool = True,
) -> QlibConversionResult:
    """Convert parquet quant data into Qlib native bin_data artifacts."""

    normalized_market = normalize_market(market)
    output_market_dir = Path(output_dir) / normalized_market
    output_market_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_market_dir / "qlib_conversion_summary.json"
    capability = check_qlib_data_capability()
    base_payload: dict[str, Any] = {
        "adapter": "qlib_bin_writer",
        "format": "bin_data",
        "market": normalized_market,
        "capability": capability.to_dict(),
        "calendar_count": 0,
        "instrument_count": 0,
        "field_count": len(QLIB_BIN_FIELDS),
        "price_adjustment_policy": PRICE_ADJUSTMENT_POLICY,
        "vwap_policy": None,
        "provider_uri": {"day": str(output_market_dir)},
        "region_mapping": {normalized_market: _qlib_region_for_market(normalized_market)[0]},
        "data_version": _read_data_version(parquet_root),
        "skip_reason": None,
        "artifacts": {"summary": str(summary_path)},
    }

    if not enabled or not capability.available:
        reason = "qlib native bin conversion disabled by caller" if not enabled else capability.skip_reason or QLIB_SKIP_REASON
        base_payload["skip_reason"] = reason
        _write_summary(summary_path, base_payload)
        return QlibConversionResult(available=False, fallback_used=True, skip_reason=reason, artifacts={"summary": str(summary_path)}, adapter="qlib_bin_writer")

    try:
        daily_bar = read_parquet("daily_bar", root=parquet_root)
        calendar_table = _read_optional_parquet("calendar", parquet_root)
        normalized_bar = normalize_qlib_bar_fields(daily_bar, normalized_market)
        calendar = build_calendar_index(calendar_table, normalized_bar, normalized_market)
        spans = _instrument_spans(normalized_bar)
        text_artifacts = write_qlib_text_files(calendar, spans, output_market_dir, normalized_market)
        init_qlib_provider(output_market_dir, normalized_market)
        feature_artifacts = write_qlib_features(normalized_bar, calendar, output_market_dir)
        readback = verify_qlib_bin_readback(output_market_dir, normalized_market, normalized_bar, calendar)
    except Exception as exc:
        reason = f"qlib native bin conversion failed: {type(exc).__name__}: {exc}"
        base_payload["skip_reason"] = reason
        base_payload["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _write_summary(summary_path, base_payload)
        return QlibConversionResult(available=False, fallback_used=True, skip_reason=reason, artifacts={"summary": str(summary_path)}, adapter="qlib_bin_writer")

    artifacts = {**text_artifacts, **feature_artifacts, "summary": str(summary_path)}
    payload = {
        **base_payload,
        "calendar_count": len(calendar.calendar),
        "instrument_count": int(spans["instrument"].nunique()),
        "field_count": len(QLIB_BIN_FIELDS),
        "vwap_policy": normalized_bar.attrs.get("vwap_policy"),
        "readback": readback,
        "skip_reason": None,
        "artifacts": artifacts,
    }
    _write_summary(summary_path, payload)
    return QlibConversionResult(available=True, fallback_used=False, skip_reason=None, artifacts=artifacts, adapter="qlib_bin_writer")
