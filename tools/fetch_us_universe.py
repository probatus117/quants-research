"""Fetch US stock daily bars via yfinance for Qlib native research.

Usage:
  conda run -n stock-skills-2 python tools/fetch_us_universe.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.market_config import get_market_config, normalize_market
from src.quant.data.providers.yfinance_provider import YFinanceProvider, YFinanceProviderError
from src.quant.data.schema import validate_schema
from src.quant.data.storage import write_parquet

# Curated US stock universe: ~80 liquid names across sectors
# Selected for: liquidity, data availability 2022-2024, sector diversity
US_UNIVERSE = [
    # Technology (20)
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "AMD", "ADBE",
    "CRM", "ORCL", "CSCO", "INTC", "QCOM", "TXN", "NOW", "INTU",
    "AMAT", "MU", "PANW", "SNOW",
    # Healthcare (12)
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT",
    "BMY", "AMGN", "GILD", "ISRG",
    # Financials (10)
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "AXP", "V", "MA",
    # Consumer Discretionary (12)
    "AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "TJX",
    "BKNG", "DIS", "CMG", "RCL",
    # Industrials (8)
    "CAT", "BA", "GE", "RTX", "HON", "UPS", "UNP", "LMT",
    # Energy (5)
    "XOM", "CVX", "COP", "EOG", "SLB",
    # Consumer Staples (5)
    "PG", "KO", "PEP", "COST", "WMT",
    # Utilities / Real Estate / Materials (5)
    "NEE", "SO", "PLD", "AMT", "LIN",
    # Communications (3)
    "NFLX", "TMUS", "T",
]

BENCHMARK = "^GSPC"
START_DATE = "2022-01-01"
END_DATE = "2024-12-31"
OUTPUT_DIR = Path("data/quant/parquet")


def main() -> int:
    market = "us"
    cfg = get_market_config(market)
    symbols = US_UNIVERSE
    all_symbols = symbols + [BENCHMARK]

    print(f"Fetching {len(symbols)} US stocks + benchmark {BENCHMARK}...")
    print(f"Date range: {START_DATE} to {END_DATE}")

    provider = YFinanceProvider(auto_adjust=False)

    # Fetch daily bars
    try:
        daily_bar = provider.get_daily_bar(
            market=market,
            start_date=START_DATE,
            end_date=END_DATE,
            symbols=all_symbols,
        )
    except YFinanceProviderError as exc:
        print(f"ERROR: yfinance fetch failed: {exc}")
        return 1

    print(f"Fetched {len(daily_bar)} rows, {daily_bar['symbol'].nunique()} unique symbols")

    # Separate benchmark from stock data
    from src.quant.data.schema import normalize_symbol
    bench_symbol = normalize_symbol(BENCHMARK, market)
    bench_mask = daily_bar["symbol"] == bench_symbol
    bench_df = daily_bar[bench_mask].copy()
    stock_df = daily_bar[~bench_mask].copy()
    print(f"Benchmark {bench_symbol}: {len(bench_df)} rows")

    # Validate and write daily_bar (stocks only)
    daily_bar_out = validate_schema(stock_df, "daily_bar")
    bar_path = write_parquet(daily_bar_out, "daily_bar")
    print(f"Written daily_bar: {bar_path} ({len(daily_bar_out)} rows)")

    # Build calendar from stock trading dates
    calendar = (
        stock_df[["date", "market"]]
        .drop_duplicates()
        .sort_values("date")
        .copy()
    )
    calendar["is_open"] = True
    calendar = validate_schema(calendar.reset_index(drop=True), "calendar")
    cal_path = write_parquet(calendar, "calendar")
    print(f"Written calendar: {cal_path} ({len(calendar)} rows)")

    # Build dim_security (universe definition)
    symbol_info = []
    industries = [
        "Technology", "Technology", "Technology", "Technology", "Technology",
        "Technology", "Technology", "Technology", "Technology", "Technology",
        "Technology", "Technology", "Technology", "Technology", "Technology",
        "Technology", "Technology", "Technology", "Technology", "Technology",
        "Healthcare", "Healthcare", "Healthcare", "Healthcare", "Healthcare",
        "Healthcare", "Healthcare", "Healthcare", "Healthcare", "Healthcare",
        "Healthcare", "Healthcare",
        "Financials", "Financials", "Financials", "Financials", "Financials",
        "Financials", "Financials", "Financials", "Financials", "Financials",
        "Consumer Discretionary", "Consumer Discretionary", "Consumer Discretionary",
        "Consumer Discretionary", "Consumer Discretionary", "Consumer Discretionary",
        "Consumer Discretionary", "Consumer Discretionary", "Consumer Discretionary",
        "Consumer Discretionary", "Consumer Discretionary", "Consumer Discretionary",
        "Industrials", "Industrials", "Industrials", "Industrials", "Industrials",
        "Industrials", "Industrials", "Industrials",
        "Energy", "Energy", "Energy", "Energy", "Energy",
        "Consumer Staples", "Consumer Staples", "Consumer Staples",
        "Consumer Staples", "Consumer Staples",
        "Utilities", "Utilities", "Real Estate", "Real Estate", "Materials",
        "Communications", "Communications", "Communications",
    ]

    for symbol, industry in zip(symbols, industries):
        symbol_info.append({
            "market": market,
            "symbol": symbol,
            "name": symbol,
            "exchange": "NASDAQ" if symbol in {
                "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "AMD", "ADBE",
                "CRM", "ORCL", "CSCO", "INTC", "QCOM", "TXN", "NOW", "INTU",
                "AMAT", "MU", "PANW", "SNOW", "AMZN", "TSLA", "NFLX", "TMUS",
                "ISRG", "GILD", "SBUX", "COST", "CMG", "BKNG", "RCL",
            } else "NYSE",
            "currency": cfg.currency,
            "industry": industry,
            "market_cap_bucket": "large",
            "list_date": "2000-01-01",
            "delist_date": "",
            "universe": "us_qlib_native",
            "is_member": True,
        })

    dim_security = validate_schema(pd.DataFrame(symbol_info), "dim_security")
    dim_path = write_parquet(dim_security, "dim_security")
    print(f"Written dim_security: {dim_path} ({len(dim_security)} rows)")

    # daily_basic is not required by Qlib Alpha158 pipeline (uses daily_bar OHLCV only).
    # yfinance does not provide reliable fundamentals, so daily_basic is skipped.
    # The Qlib native workflow (Alpha158 + LightGBM + backtest) only needs daily_bar + calendar.

    # Write data_version
    version_payload = {
        "update_time": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance",
        "market": market,
        "base_currency": cfg.currency,
        "benchmark": cfg.benchmark_symbol,
        "start_date": str(daily_bar_out["date"].min()),
        "end_date": str(daily_bar_out["date"].max()),
        "row_count": {
            "daily_bar": int(len(daily_bar_out)),
            "calendar": int(len(calendar)),
            "dim_security": int(len(dim_security)),
        },
        "symbol_count": int(daily_bar_out["symbol"].nunique()),
    }
    version_dir = Path("data/quant")
    version_dir.mkdir(parents=True, exist_ok=True)
    version_path = version_dir / "data_version.json"
    version_path.write_text(json.dumps(version_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Written data_version: {version_path}")

    # Summary
    print("\n=== Fetch Summary ===")
    print(f"Symbols fetched: {daily_bar_out['symbol'].nunique()}")
    print(f"Date range: {daily_bar_out['date'].min()} to {daily_bar_out['date'].max()}")
    print(f"Total rows: {len(daily_bar_out)}")
    print(f"Benchmark: {BENCHMARK}")
    print("\nNext steps:")
    print("  conda run -n stock-skills-2 python tools/quant_qlib.py convert --market us")
    print("  conda run -n stock-skills-2 python tools/quant_qlib.py run --market us --register")
    return 0


if __name__ == "__main__":
    sys.exit(main())
