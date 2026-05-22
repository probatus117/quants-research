from __future__ import annotations

import numpy as np

from src.quant.backtest.signal_builder import (
    SignalConfig,
    build_composite_signal,
    build_single_factor_signal,
    write_signal,
)
from src.quant.data.storage import read_parquet


def _factor_rows():
    import pandas as pd

    rows = []
    values = {
        "AAA": {"value_bp": 1.0, "momentum_12_1": 2.0, "lowvol_60d": 3.0},
        "BBB": {"value_bp": 2.0, "momentum_12_1": 1.0, "lowvol_60d": 0.0},
        "CCC": {"value_bp": 3.0, "momentum_12_1": 0.0, "lowvol_60d": 1.0},
    }
    for symbol, factors in values.items():
        for factor_name, zscore in factors.items():
            rows.append(
                {
                    "date": "2024-01-02",
                    "symbol": symbol,
                    "factor_name": factor_name,
                    "zscore": zscore,
                    "universe": "sample_a",
                }
            )
    return pd.DataFrame(rows)


def test_build_single_factor_signal_normalizes_by_date() -> None:
    signal = build_single_factor_signal(_factor_rows(), "value_bp")

    assert signal["signal_name"].unique().tolist() == ["value_bp"]
    assert np.isclose(signal["score"].mean(), 0.0)
    assert np.isclose(signal["score"].std(), 1.0)
    assert signal.iloc[0]["symbol"] == "CCC"


def test_build_composite_signal_uses_composite_v1_formula() -> None:
    signal = build_composite_signal(_factor_rows(), SignalConfig())
    raw_by_symbol = dict(zip(signal["symbol"], signal["raw_score"]))

    assert np.isclose(raw_by_symbol["AAA"], 0.34 * 1.0 + 0.33 * 2.0 + 0.33 * 3.0)
    assert np.isclose(raw_by_symbol["BBB"], 0.34 * 2.0 + 0.33 * 1.0 + 0.33 * 0.0)
    assert np.isclose(signal["score"].mean(), 0.0)
    assert signal.iloc[0]["symbol"] == "AAA"


def test_write_signal_round_trip(tmp_path) -> None:
    signal = build_composite_signal(_factor_rows())
    path = write_signal(signal, tmp_path)

    assert path.name == "data.parquet"
    restored = read_parquet("signal", root=tmp_path)
    assert restored.equals(signal)
