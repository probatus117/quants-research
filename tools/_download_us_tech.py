"""One-shot: download US tech stock data via yfinance provider."""
import sys, time, json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.quant.data.providers.yfinance_provider import YFinanceProvider
from src.quant.data.market_config import get_market_config
from src.quant.data.storage import write_parquet
from src.quant.data.quality_check import dataframe_hash

SYMBOLS = [
    'NVDA', 'AVGO', 'QCOM',
    'MSFT', 'ADBE', 'CRM', 'NOW',
    'PANW', 'FTNT',
    'GOOGL', 'META', 'AAPL', 'NFLX',
    'CSCO', 'ANET',
]

MARKET = "us"
CHUNK = 4

provider = YFinanceProvider()
all_frames = []
errors = []

print(f"Downloading {len(SYMBOLS)} US tech stocks in chunks of {CHUNK}...", flush=True)
start = time.time()

for i in range(0, len(SYMBOLS), CHUNK):
    chunk = SYMBOLS[i:i+CHUNK]
    try:
        df = provider.get_daily_bar(
            market=MARKET,
            start_date="2021-01-01",
            end_date="2026-05-23",
            symbols=chunk,
        )
        all_frames.append(df)
        rows = len(df)
        syms = df['symbol'].nunique()
        dr = f"{df['date'].min()}~{df['date'].max()}"
        print(f"  [{i+1}-{min(i+CHUNK, len(SYMBOLS))}] {chunk}: {rows} rows, {syms} symbols, {dr}", flush=True)
    except Exception as e:
        print(f"  [{i+1}-{min(i+CHUNK, len(SYMBOLS))}] {chunk}: ERROR - {e}", flush=True)
        errors.extend(chunk)

elapsed = time.time() - start
print(f"\nDownload done in {elapsed:.0f}s", flush=True)

if not all_frames:
    print("No data downloaded!")
    sys.exit(1)

daily_bar = pd.concat(all_frames, ignore_index=True)
print(f"Combined: {len(daily_bar)} rows, {daily_bar['symbol'].nunique()} symbols")
print(f"Date range: {daily_bar['date'].min()} ~ {daily_bar['date'].max()}")

if errors:
    print(f"Failed symbols: {errors}")

# Coverage per symbol
print(f"\n{'Symbol':<7} {'Rows':>6} {'Start':>12} {'End':>12} {'Span':>7}")
print("-" * 48)
for sym in SYMBOLS:
    sub = daily_bar[daily_bar['symbol'] == sym]
    if len(sub):
        days = (pd.Timestamp(sub['date'].max()) - pd.Timestamp(sub['date'].min())).days
        print(f"  {sym:<7} {len(sub):>6} {str(sub['date'].min()):>12} {str(sub['date'].max()):>12} {days:>6}d")
    else:
        print(f"  {sym:<7} {'MISSING'}")

# Write parquet
parquet_path = write_parquet(daily_bar, "daily_bar", root="data/quant/parquet")
print(f"\nSaved: {parquet_path}")

# Write data_version.json
status = daily_bar.attrs.get("provider_status", {})
version = {
    "update_time": datetime.now(timezone.utc).isoformat(),
    "source": "yfinance",
    "market": MARKET,
    "base_currency": get_market_config(MARKET).currency,
    "benchmark": get_market_config(MARKET).benchmark,
    "start_date": str(daily_bar['date'].min()),
    "end_date": str(daily_bar['date'].max()),
    "row_count": {"daily_bar": int(len(daily_bar))},
    "hash": {"daily_bar": dataframe_hash(daily_bar)},
    "symbols": SYMBOLS,
    "failed_symbols": errors,
    "provider_status": status,
}
vpath = Path("data/quant/data_version.json")
vpath.parent.mkdir(parents=True, exist_ok=True)
vpath.write_text(json.dumps(version, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Saved: {vpath}")
print("Done!")
