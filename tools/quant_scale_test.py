"""Run Phase 7 pandas scale checks for factor/eval/backtest operations."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.quant.backtest.cost_model import CostConfig  # noqa: E402
from src.quant.backtest.pandas_runner import BacktestConfig, run_topn_backtest  # noqa: E402
from src.quant.backtest.signal_builder import SignalConfig, build_composite_signal  # noqa: E402
from src.quant.evaluation.input_builder import EvaluationInputConfig, build_evaluation_input  # noqa: E402
from src.quant.factors import LowVolatility60DFactor, Momentum121Factor, ValueBPFactor  # noqa: E402
from src.quant.factors.store import combine_and_process  # noqa: E402


def _synthetic_tables(symbol_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2023-01-02", "2024-12-31")
    symbols = [f"{i + 1:06d}" for i in range(symbol_count)]
    bar_rows = []
    basic_rows = []
    for idx, symbol in enumerate(symbols):
        base = 10.0 + idx * 0.01
        for t, date in enumerate(dates):
            close = base * (1 + 0.0002 + (idx % 9) * 0.00001) ** t
            day = date.date().isoformat()
            bar_rows.append(
                {
                    "date": day,
                    "market": "cn",
                    "symbol": symbol,
                    "adj_close": close,
                    "is_suspended": False,
                }
            )
            basic_rows.append(
                {
                    "date": day,
                    "market": "cn",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic quant scale tests")
    parser.add_argument("--sizes", default="100,500,2000")
    parser.add_argument("--output", default="data/quant/scale_test/scale_report.json")
    args = parser.parse_args(argv)
    rows = [_run_one(int(size)) for size in args.sizes.split(",") if size.strip()]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"rows": rows}, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "rows": rows}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
