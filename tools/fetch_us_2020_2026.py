"""Fetch US stock daily bars 2020-2026 for Qlib workflow."""
from __future__ import annotations

import sys, json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.data.market_config import get_market_config
from src.quant.data.providers.yfinance_provider import YFinanceProvider, YFinanceProviderError
from src.quant.data.schema import validate_schema, normalize_symbol
from src.quant.data.storage import write_parquet

US_UNIVERSE = [
    "AAPL","MSFT","NVDA","GOOGL","META","AVGO","AMD","ADBE",
    "CRM","ORCL","CSCO","INTC","QCOM","TXN","NOW","INTU",
    "AMAT","MU","PANW","SNOW","CRWD","PLTR",
    "JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","ABT","BMY","AMGN","GILD","ISRG",
    "JPM","BAC","WFC","GS","MS","C","BLK","AXP","V","MA",
    "AMZN","TSLA","HD","NKE","MCD","SBUX","LOW","TJX","BKNG","DIS","CMG","RCL",
    "CAT","BA","GE","RTX","HON","UPS","UNP","LMT",
    "XOM","CVX","COP","EOG","SLB",
    "PG","KO","PEP","COST","WMT",
    "NEE","SO","PLD","AMT","LIN","NFLX","TMUS","T",
]

BENCHMARKS = ["SPY"]
START_DATE = "2019-12-15"
END_DATE = "2026-05-23"

MARKET = "us"

def main() -> int:
    cfg = get_market_config(MARKET)
    all_symbols = US_UNIVERSE + BENCHMARKS

    print(f"Fetching {len(US_UNIVERSE)} US stocks + SPY...")
    print(f"Date range: {START_DATE} to {END_DATE}")

    provider = YFinanceProvider(auto_adjust=False)
    try:
        daily_bar = provider.get_daily_bar(market=MARKET, start_date=START_DATE, end_date=END_DATE, symbols=all_symbols)
    except YFinanceProviderError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Fetched {len(daily_bar)} rows, {daily_bar['symbol'].nunique()} unique symbols")

    bench_symbol = normalize_symbol("SPY", MARKET)
    bench_mask = daily_bar["symbol"] == bench_symbol
    stock_df = daily_bar[~bench_mask].copy()
    bench_df = daily_bar[bench_mask].copy()
    print(f"Stocks: {stock_df['symbol'].nunique()} unique, Benchmark SPY: {len(bench_df)} rows")

    # daily_bar
    daily_bar_out = validate_schema(stock_df, "daily_bar")
    write_parquet(daily_bar_out, "daily_bar")
    print(f"daily_bar: {len(daily_bar_out)} rows ({daily_bar_out['date'].min()} to {daily_bar_out['date'].max()})")

    # calendar with buffer
    cal = stock_df[["date", "market"]].drop_duplicates().sort_values("date").copy()
    cal["is_open"] = True
    last_date = cal["date"].max()
    buffer_dates = pd.date_range(pd.to_datetime(last_date) + pd.Timedelta(days=1), periods=5, freq="B")
    buffer = pd.DataFrame([{"date": d.strftime("%Y-%m-%d"), "market": MARKET, "is_open": True} for d in buffer_dates])
    cal = pd.concat([cal, buffer], ignore_index=True)
    cal = validate_schema(cal.reset_index(drop=True), "calendar")
    write_parquet(cal, "calendar")
    print(f"calendar: {len(cal)} rows (last: {cal['date'].max()})")

    # dim_security
    industries = (
        ["Technology"]*22 + ["Healthcare"]*12 + ["Financials"]*10 + ["Consumer Discretionary"]*12 +
        ["Industrials"]*8 + ["Energy"]*5 + ["Consumer Staples"]*5 + ["Other"]*8
    )
    nasdaq_set = {"AAPL","MSFT","NVDA","GOOGL","META","AVGO","AMD","ADBE","CRM","ORCL",
                  "CSCO","INTC","QCOM","TXN","NOW","INTU","AMAT","MU","PANW","SNOW",
                  "CRWD","PLTR","AMZN","TSLA","NFLX","TMUS","ISRG","GILD","SBUX","COST","CMG","BKNG","RCL"}
    rows = []
    for sym, ind in zip(US_UNIVERSE, industries):
        rows.append({"market": MARKET, "symbol": sym, "name": sym,
                     "exchange": "NASDAQ" if sym in nasdaq_set else "NYSE",
                     "currency": cfg.currency, "industry": ind,
                     "market_cap_bucket": "large", "list_date": "2000-01-01", "delist_date": "",
                     "universe": "us_qlib_native", "is_member": True})
    dim = validate_schema(pd.DataFrame(rows), "dim_security")
    write_parquet(dim, "dim_security")
    print(f"dim_security: {len(dim)} rows")

    # data_version
    payload = {
        "update_time": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance", "market": MARKET, "base_currency": cfg.currency,
        "benchmark": "^GSPC",
        "start_date": str(daily_bar_out["date"].min()),
        "end_date": str(daily_bar_out["date"].max()),
        "symbol_count": int(daily_bar_out["symbol"].nunique()),
    }
    vdir = Path("data/quant")
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "data_version.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
