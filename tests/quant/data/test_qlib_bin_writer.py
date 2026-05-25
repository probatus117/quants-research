from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import src.quant.data.qlib_bin_writer as qlib_bin_writer
from src.quant.data.qlib_bin_writer import (
    build_calendar_index,
    build_qlib_instrument_name,
    check_qlib_data_capability,
    convert_parquet_to_qlib_bin,
    normalize_qlib_bar_fields,
    write_qlib_text_files,
)
from src.quant.data.storage import write_parquet


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "market": "cn",
                "symbol": "000001",
                "exchange": "SH",
                "open": 9.0,
                "high": 11.0,
                "low": 8.0,
                "close": 10.0,
                "adj_close": 20.0,
                "volume": 50.0,
                "amount": 1000.0,
            },
            {
                "date": "2024-01-03",
                "market": "cn",
                "symbol": "000001",
                "exchange": "SH",
                "open": 11.0,
                "high": 13.0,
                "low": 10.0,
                "close": 12.0,
                "adj_close": 24.0,
                "volume": 0.0,
                "amount": 0.0,
            },
            {
                "date": "2024-01-03",
                "market": "cn",
                "symbol": "000002",
                "exchange": "SZ",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 0.0,
                "adj_close": 1.0,
                "volume": 10.0,
                "amount": 10.0,
            },
        ]
    )


def test_instrument_name_mapping() -> None:
    assert build_qlib_instrument_name("000001", "SH", "cn") == "sh000001"
    assert build_qlib_instrument_name("000001", "SZ", "cn") == "sz000001"
    assert build_qlib_instrument_name("AAPL", "NASDAQ", "us") == "AAPL"
    assert build_qlib_instrument_name("7203.T", "TSE", "jp") == "7203.T"
    with pytest.raises(ValueError, match="requires exchange"):
        build_qlib_instrument_name("000001", None, "cn")


def test_normalize_adjustment_vwap_and_change() -> None:
    normalized = normalize_qlib_bar_fields(_bars(), "cn")
    first = normalized[normalized["instrument"] == "sh000001"].iloc[0]
    second = normalized[normalized["instrument"] == "sh000001"].iloc[1]
    zero_close = normalized[normalized["instrument"] == "sz000002"].iloc[0]

    assert first["factor"] == 2.0
    assert first["open"] == 18.0
    assert first["close"] == 20.0
    assert first["vwap"] == 40.0
    assert second["change"] == pytest.approx(0.2)
    assert zero_close["factor"] == 1.0
    assert "amount / volume" in normalized.attrs["vwap_policy"]


def test_normalize_vwap_fallback_when_amount_missing() -> None:
    bars = _bars().drop(columns=["amount"])
    normalized = normalize_qlib_bar_fields(bars, "cn")
    first = normalized[normalized["instrument"] == "sh000001"].iloc[0]
    assert first["vwap"] == pytest.approx((22.0 + 16.0 + 20.0) / 3)
    assert "fallback" in normalized.attrs["vwap_policy"]


def test_calendar_and_instrument_text_files(tmp_path: Path) -> None:
    calendar = pd.DataFrame(
        [
            {"date": "2024-01-01", "market": "cn", "is_open": False},
            {"date": "2024-01-02", "market": "cn", "is_open": True},
            {"date": "2024-01-03", "market": "cn", "is_open": True},
        ]
    )
    normalized = normalize_qlib_bar_fields(_bars(), "cn")
    cal = build_calendar_index(calendar, normalized, "cn")
    spans = normalized.groupby("instrument", as_index=False).agg(start_datetime=("date", "min"), end_datetime=("date", "max"))

    artifacts = write_qlib_text_files(cal, spans, tmp_path, "cn")

    assert Path(artifacts["calendar"]).read_text(encoding="utf-8").splitlines() == ["2024-01-02", "2024-01-03"]
    assert Path(artifacts["instruments"]).read_text(encoding="utf-8").splitlines()[0] == "sh000001\t2024-01-02\t2024-01-03"


def test_convert_graceful_skip_when_qlib_data_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qlib_bin_writer,
        "check_qlib_data_capability",
        lambda: qlib_bin_writer.QlibDataCapability(False, False, "missing qlib data layer"),
    )
    result = convert_parquet_to_qlib_bin(parquet_root=tmp_path / "parquet", output_dir=tmp_path / "qlib_bin", market="cn")

    summary_path = tmp_path / "qlib_bin" / "cn" / "qlib_conversion_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert result.fallback_used is True
    assert summary["capability"]["qlib_data_available"] is False
    assert summary["skip_reason"] == "missing qlib data layer"


def test_convert_real_readback_when_qlib_data_available(tmp_path: Path) -> None:
    if not check_qlib_data_capability().available:
        pytest.skip("Qlib data layer is not installed")
    write_parquet(_bars(), "daily_bar", root=tmp_path / "parquet")
    write_parquet(
        pd.DataFrame(
            [
                {"date": "2024-01-02", "market": "cn", "is_open": True},
                {"date": "2024-01-03", "market": "cn", "is_open": True},
            ]
        ),
        "calendar",
        root=tmp_path / "parquet",
    )

    result = convert_parquet_to_qlib_bin(parquet_root=tmp_path / "parquet", output_dir=tmp_path / "qlib_bin", market="cn")

    summary = json.loads((tmp_path / "qlib_bin" / "cn" / "qlib_conversion_summary.json").read_text(encoding="utf-8"))
    assert result.available is True
    assert summary["calendar_count"] == 2
    assert summary["instrument_count"] == 2
    assert (tmp_path / "qlib_bin" / "cn" / "features" / "sh000001" / "close.day.bin").exists()
