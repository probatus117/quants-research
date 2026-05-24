"""Build daily_basic from yfinance quarterly balance sheets + daily prices."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from src.quant.data.storage import read_parquet, write_parquet
from src.quant.data.schema import validate_schema

SYMBOLS = [
    'NVDA', 'AVGO', 'QCOM',
    'MSFT', 'ADBE', 'CRM', 'NOW',
    'PANW', 'FTNT',
    'GOOGL', 'META', 'AAPL', 'NFLX',
    'CSCO', 'ANET',
]

print(f"Building daily_basic for {len(SYMBOLS)} stocks...")

# Load daily prices
daily_bar = read_parquet("daily_bar", root="data/quant/parquet")
daily_bar['date'] = pd.to_datetime(daily_bar['date'])
prices = daily_bar[['date', 'symbol', 'close']].copy()

rows = []
for i, sym in enumerate(SYMBOLS):
    try:
        ticker = yf.Ticker(sym)
        bs = ticker.quarterly_balance_sheet
        if bs is None or bs.empty:
            print(f"  {sym}: no balance sheet data", flush=True)
            continue

        # Book value per share
        bv_field = None
        for f in ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest']:
            if f in bs.index:
                bv_field = f
                break
        shares_field = 'Ordinary Shares Number' if 'Ordinary Shares Number' in bs.index else None

        if not bv_field or not shares_field:
            print(f"  {sym}: missing BV or shares field", flush=True)
            continue

        bv = bs.loc[bv_field]
        shares = bs.loc[shares_field]
        bvps = pd.DataFrame({'date': pd.to_datetime(bv.index.values).tz_localize(None), 'bvps': (bv.values / shares.values).astype(float)})
        bvps = bvps.sort_values('date')
        bvps['date'] = bvps['date'].astype('datetime64[ns]')

        # Merge with daily prices
        sym_prices = prices[prices['symbol'] == sym][['date', 'close']].copy()
        sym_prices['date'] = pd.to_datetime(sym_prices['date']).astype('datetime64[ns]')
        sym_prices = sym_prices.sort_values('date')
        sym_data = pd.merge_asof(sym_prices, bvps, on='date', direction='backward')
        sym_data['pb'] = sym_data['close'] / sym_data['bvps'].replace(0, np.nan)
        sym_data['pb'] = sym_data['pb'].replace([np.inf, -np.inf], np.nan)
        sym_data['symbol'] = sym
        sym_data['market'] = 'us'
        sym_data['currency'] = 'USD'
        sym_data['pe_ttm'] = np.nan
        sym_data['total_mv'] = np.nan
        sym_data['circ_mv'] = np.nan
        sym_data['total_share'] = np.nan
        sym_data['float_share'] = np.nan
        sym_data['dividend_yield'] = np.nan
        sym_data['turnover_rate'] = np.nan

        valid = sym_data['pb'].notna()
        print(f"  {sym}: {valid.sum()}/{len(sym_data)} days with PB, range=[{sym_data['pb'].min():.1f}, {sym_data['pb'].max():.1f}]", flush=True)
        rows.append(sym_data[['date','market','symbol','currency','pe_ttm','pb','total_mv','circ_mv','total_share','float_share','dividend_yield','turnover_rate']])
    except Exception as e:
        print(f"  {sym}: ERROR {e}", flush=True)

if not rows:
    print("No data built!")
    sys.exit(1)

daily_basic = pd.concat(rows, ignore_index=True)
daily_basic['date'] = daily_basic['date'].dt.date.astype(str)
daily_basic = daily_basic.sort_values(['date', 'symbol']).reset_index(drop=True)

print(f"\nTotal: {len(daily_basic)} rows, {daily_basic['symbol'].nunique()} symbols")
print(f"PB coverage: {daily_basic['pb'].notna().sum()}/{len(daily_basic)}")
print(f"PB range: [{daily_basic['pb'].min():.2f}, {daily_basic['pb'].max():.2f}]")
print(f"Date range: {daily_basic['date'].min()} ~ {daily_basic['date'].max()}")

write_parquet(daily_basic, "daily_basic", root="data/quant/parquet")
print("Saved daily_basic")
