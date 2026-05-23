"""Backtest helpers for quant research."""

from src.quant.backtest.cost_model import CostConfig
from src.quant.backtest.metrics import calculate_metrics
from src.quant.backtest.pandas_runner import BacktestConfig, BacktestResult, run_topn_backtest
from src.quant.backtest.strategies import BaseStrategy, TopNEqualWeight
from src.quant.backtest.walk_forward import walk_forward_metrics
from src.quant.backtest.signal_builder import (
    COMPOSITE_V1_WEIGHTS,
    SignalConfig,
    build_composite_signal,
    build_single_factor_signal,
    write_signal,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BaseStrategy",
    "COMPOSITE_V1_WEIGHTS",
    "CostConfig",
    "SignalConfig",
    "TopNEqualWeight",
    "build_composite_signal",
    "build_single_factor_signal",
    "calculate_metrics",
    "run_topn_backtest",
    "walk_forward_metrics",
    "write_signal",
]
