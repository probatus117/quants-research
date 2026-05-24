"""Run Phase 7 pandas scale checks for factor/eval/backtest operations."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.backtest.cost_model import CostConfig  # noqa: E402
from src.quant.backtest.pandas_runner import BacktestConfig, run_topn_backtest  # noqa: E402
from src.quant.backtest.signal_builder import SignalConfig, build_composite_signal  # noqa: E402
from src.quant.data.duckdb_query import check_duckdb_capability, query_table  # noqa: E402
from src.quant.evaluation.input_builder import EvaluationInputConfig, build_evaluation_input  # noqa: E402
from src.quant.factors import LowVolatility60DFactor, Momentum121Factor, ValueBPFactor  # noqa: E402
from src.quant.factors.store import combine_and_process  # noqa: E402


def _synthetic_tables(symbol_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2023-01-02", "2024-12-31")
    markets = ("cn", "us", "jp")
    symbols = [f"{markets[i % len(markets)]}_{i + 1:06d}" for i in range(symbol_count)]
    bar_rows = []
    basic_rows = []
    for idx, symbol in enumerate(symbols):
        market = markets[idx % len(markets)]
        base = 10.0 + idx * 0.01
        for t, date in enumerate(dates):
            close = base * (1 + 0.0002 + (idx % 9) * 0.00001) ** t
            day = date.date().isoformat()
            bar_rows.append(
                {
                    "date": day,
                    "market": market,
                    "symbol": symbol,
                    "adj_close": close,
                    "is_suspended": False,
                }
            )
            basic_rows.append(
                {
                    "date": day,
                    "market": market,
                    "symbol": symbol,
                    "pb": 0.8 + (idx % 50) * 0.02,
                    "total_mv": close * (100_000_000 + idx * 1000) / 1_000_000,
                }
            )
    return pd.DataFrame(bar_rows), pd.DataFrame(basic_rows)


def _run_one(symbol_count: int) -> dict[str, object]:
    daily_bar, daily_basic = _synthetic_tables(symbol_count)
    started = time.perf_counter()
    value = ValueBPFactor().compute(daily_basic).values
    momentum = Momentum121Factor().compute(daily_bar).values
    lowvol = LowVolatility60DFactor().compute(daily_bar).values
    factor_values = combine_and_process([value, momentum, lowvol])
    factor_seconds = time.perf_counter() - started

    started = time.perf_counter()
    evaluation = build_evaluation_input(
        factor_values,
        daily_bar,
        EvaluationInputConfig("momentum_12_1", periods=(5, 20, 60)),
    )
    eval_seconds = time.perf_counter() - started

    started = time.perf_counter()
    signal = build_composite_signal(
        factor_values,
        SignalConfig(factor_column="zscore", min_factors=2),
    )
    result = run_topn_backtest(
        signal,
        daily_bar,
        BacktestConfig(top_n=min(10, symbol_count), cost=CostConfig(min_cost=0)),
    )
    backtest_seconds = time.perf_counter() - started
    return {
        "symbols": symbol_count,
        "daily_rows": int(len(daily_bar)),
        "factor_rows": int(len(factor_values)),
        "evaluation_rows": int(len(evaluation)),
        "portfolio_rows": int(len(result.portfolio_value)),
        "factor_groupby_seconds": round(factor_seconds, 4),
        "evaluation_merge_seconds": round(eval_seconds, 4),
        "backtest_pivot_seconds": round(backtest_seconds, 4),
    }


def _run_duckdb_compare(symbol_count: int) -> dict[str, object]:
    daily_bar, _ = _synthetic_tables(symbol_count)
    capability = check_duckdb_capability()
    if not capability.available:
        return {
            "symbols": symbol_count,
            "daily_rows": int(len(daily_bar)),
            "duckdb_available": False,
            "skip_reason": capability.skip_reason,
        }

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        table_dir = root / "daily_bar"
        table_dir.mkdir(parents=True, exist_ok=True)
        daily_bar.to_parquet(table_dir / "data.parquet", index=False)

        started = time.perf_counter()
        pandas_rows = daily_bar[daily_bar["market"].isin(["cn", "us", "jp"])].copy()
        pandas_market_counts = pandas_rows.groupby("market")["symbol"].nunique().to_dict()
        pandas_seconds = time.perf_counter() - started

        started = time.perf_counter()
        duckdb_result = query_table("daily_bar", root=root, filters={"market": ["cn", "us", "jp"]})
        duckdb_market_counts = duckdb_result.frame.groupby("market")["symbol"].nunique().to_dict()
        duckdb_seconds = time.perf_counter() - started

    return {
        "symbols": symbol_count,
        "markets": ["cn", "us", "jp"],
        "daily_rows": int(len(daily_bar)),
        "duckdb_available": True,
        "pandas_rows": int(len(pandas_rows)),
        "duckdb_rows": int(len(duckdb_result.frame)),
        "pandas_market_symbol_counts": {str(k): int(v) for k, v in pandas_market_counts.items()},
        "duckdb_market_symbol_counts": {str(k): int(v) for k, v in duckdb_market_counts.items()},
        "pandas_filter_seconds": round(pandas_seconds, 4),
        "duckdb_filter_seconds": round(duckdb_seconds, 4),
        "duckdb_engine": duckdb_result.engine,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic quant scale tests")
    parser.add_argument("--sizes", default="100,500,2000")
    parser.add_argument("--output", default="data/quant/scale_test/scale_report.json")
    parser.add_argument("--duckdb", action="store_true", help="Also compare pandas filter vs DuckDB parquet query")
    args = parser.parse_args(argv)
    rows = [_run_one(int(size)) for size in args.sizes.split(",") if size.strip()]
    duckdb_rows = [_run_duckdb_compare(int(size)) for size in args.sizes.split(",") if size.strip()] if args.duckdb else []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"rows": rows, "duckdb_rows": duckdb_rows}
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **payload}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
