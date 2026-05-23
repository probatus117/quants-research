"""Probe live quant providers and write Phase 7 coverage artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.providers.yfinance_provider import HAS_YFINANCE, YFinanceProvider, YFinanceProviderError  # noqa: E402
from src.quant.data.schema import validate_schema  # noqa: E402


DEFAULT_SYMBOLS = {
    "us": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "BRK.B", "JPM", "XOM", "UNH"],
    "jp": ["7203.T", "6758.T", "9984.T", "8306.T", "9432.T", "6861.T", "8035.T", "6098.T", "4063.T", "4519.T"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe yfinance market coverage")
    parser.add_argument("--output-dir", default="data/quant/provider_probe", help="Probe artifact directory")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-01-01")
    return parser


def run_probe(output_dir: str | Path, start_date: str, end_date: str) -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    provider = YFinanceProvider()
    payload: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": "yfinance",
        "has_yfinance": HAS_YFINANCE,
        "start_date": start_date,
        "end_date": end_date,
        "markets": {},
    }
    coverage_rows = []
    for market, symbols in DEFAULT_SYMBOLS.items():
        market_result: dict[str, object] = {"symbols": symbols}
        try:
            bars = provider.get_daily_bar(market=market, start_date=start_date, end_date=end_date, symbols=symbols)
            calendar = provider.get_calendar(market=market, start_date=start_date, end_date=end_date)
            validate_schema(bars, "daily_bar")
            validate_schema(calendar, "calendar")
            coverage = {
                "daily_bar_rows": int(len(bars)),
                "symbols_returned": int(bars["symbol"].nunique()),
                "calendar_rows": int(len(calendar)),
                "fields": sorted(bars.columns.tolist()),
                "provider_status": provider.last_status.as_dict(),
                "skip_reason": "",
            }
            market_result.update(coverage)
            coverage_rows.append({"market": market, **coverage})
        except (YFinanceProviderError, Exception) as exc:
            skip_reason = str(exc)
            market_result.update(
                {
                    "daily_bar_rows": 0,
                    "symbols_returned": 0,
                    "calendar_rows": 0,
                    "fields": [],
                    "provider_status": provider.last_status.as_dict(),
                    "skip_reason": skip_reason,
                }
            )
            coverage_rows.append({"market": market, "skip_reason": skip_reason})
        payload["markets"][market] = market_result

    probe_path = output / "provider_probe.json"
    coverage_path = output / "coverage_report.json"
    probe_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    coverage_path.write_text(json.dumps({"rows": coverage_rows}, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"provider_probe": str(probe_path), "coverage_report": str(coverage_path), "payload": payload}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_probe(args.output_dir, args.start_date, args.end_date)
    print(json.dumps({k: v for k, v in result.items() if k != "payload"}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
