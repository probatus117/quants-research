"""Generate deterministic Phase 7 multi-market quant fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("tests/fixtures/quant")
INDUSTRIES = ("Technology", "Healthcare", "Financials", "Industrials", "Consumer", "Energy", "Utilities", "Materials")
BUCKETS = ("large", "mid", "small")


def _hash_manifest(directory: Path) -> None:
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.glob("sample_*.csv"))}
    (directory / "sample_hashes.json").write_text(
        json.dumps(hashes, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_cn_fixture() -> None:
    directory = ROOT / "cn"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("sample_daily_bar.csv", "sample_daily_basic.csv", "sample_calendar.csv", "sample_universe.csv"):
        shutil.copyfile(ROOT / name, directory / name)
    _hash_manifest(directory)


def _symbols_for(market: str) -> list[str]:
    if market == "us":
        bases = [
            "AAPL",
            "MSFT",
            "NVDA",
            "AMZN",
            "META",
            "GOOGL",
            "BRK.B",
            "JPM",
            "XOM",
            "UNH",
            "V",
            "MA",
            "HD",
            "PG",
            "COST",
            "AVGO",
            "LLY",
            "MRK",
            "ABBV",
            "PEP",
            "KO",
            "CSCO",
            "CRM",
            "ORCL",
            "AMD",
            "NFLX",
            "ADBE",
            "WMT",
            "BAC",
            "CVX",
        ]
        return bases + [f"US{i:03d}" for i in range(31, 61)]
    return [f"{7200 + i}.T" for i in range(60)]


def _generate_market(market: str, currency: str, exchange: str) -> None:
    directory = ROOT / market
    directory.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2022-01-03", "2024-12-31")
    symbols = _symbols_for(market)
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "market": market, "is_open": True}).to_csv(
        directory / "sample_calendar.csv",
        index=False,
    )

    universe_rows: list[dict[str, object]] = []
    bar_rows: list[dict[str, object]] = []
    basic_rows: list[dict[str, object]] = []
    for idx, symbol in enumerate(symbols):
        industry = INDUSTRIES[idx % len(INDUSTRIES)]
        bucket = BUCKETS[idx % len(BUCKETS)]
        universe_rows.append(
            {
                "market": market,
                "symbol": symbol,
                "name": f"Sample {market.upper()} Equity {idx + 1:02d}",
                "exchange": exchange,
                "currency": currency,
                "industry": industry,
                "market_cap_bucket": bucket,
                "list_date": f"{2000 + idx % 20:04d}-{idx % 12 + 1:02d}-{idx % 27 + 1:02d}",
                "delist_date": "",
                "universe": "sample_a",
                "is_member": True,
            }
        )
        base = (80.0 if market == "us" else 1200.0) + idx * (2.7 if market == "us" else 17.0)
        trend = 0.00022 + (idx % 7) * 0.000025
        seasonal = 0.012 + (idx % 5) * 0.001
        shares = (1_000_000_000 if market == "us" else 100_000_000) + idx * 3_000_000
        for t, date in enumerate(dates):
            wave = np.sin((t + idx) / 19.0) * seasonal
            close = base * (1 + trend) ** t * (1 + wave)
            open_price = close * (1 + np.sin((t + idx) / 11.0) * 0.002)
            high = max(open_price, close) * 1.006
            low = min(open_price, close) * 0.994
            volume = int((700_000 if market == "us" else 500_000) + idx * 4300 + (t % 23) * 950)
            pe = 10 + (idx % 25) * 0.7 + (t % 60) * 0.01
            pb = 0.8 + (idx % 18) * 0.08 + (t % 45) * 0.002
            total_mv = close * shares / 1_000_000
            circ_mv = total_mv * (0.72 + (idx % 8) * 0.025)
            day = date.strftime("%Y-%m-%d")
            bar_rows.append(
                {
                    "date": day,
                    "market": market,
                    "symbol": symbol,
                    "exchange": exchange,
                    "currency": currency,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "adj_close": round(close * (1 + (idx % 3) * 0.0001), 4),
                    "volume": volume,
                    "amount": round(close * volume, 4),
                    "is_suspended": False,
                }
            )
            basic_rows.append(
                {
                    "date": day,
                    "market": market,
                    "symbol": symbol,
                    "currency": currency,
                    "pe_ttm": round(pe, 4),
                    "pb": round(pb, 4),
                    "total_mv": round(total_mv, 4),
                    "circ_mv": round(circ_mv, 4),
                    "total_share": float(shares),
                    "float_share": round(shares * 0.78, 2),
                    "dividend_yield": round(0.006 + (idx % 10) * 0.001, 4),
                    "turnover_rate": round(0.2 + (idx % 20) * 0.03 + (t % 11) * 0.002, 4),
                }
            )

    pd.DataFrame(bar_rows).to_csv(directory / "sample_daily_bar.csv", index=False)
    pd.DataFrame(basic_rows).to_csv(directory / "sample_daily_basic.csv", index=False)
    pd.DataFrame(universe_rows).to_csv(directory / "sample_universe.csv", index=False)
    _hash_manifest(directory)


def main() -> None:
    _copy_cn_fixture()
    _generate_market("us", "USD", "NASDAQ")
    _generate_market("jp", "JPY", "TSE")


if __name__ == "__main__":
    main()
