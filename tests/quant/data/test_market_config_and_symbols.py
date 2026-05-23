from __future__ import annotations

import pytest

from src.quant.data.market_config import get_market_config
from src.quant.data.schema import normalize_symbol


def test_market_config_defaults() -> None:
    assert get_market_config("us").currency == "USD"
    assert get_market_config("jp").benchmark == "nikkei225"
    assert get_market_config("cn").buy_cost == 0.0015


def test_normalize_symbol_by_market() -> None:
    assert normalize_symbol("1", "cn") == "000001"
    assert normalize_symbol("brk-b", "us") == "BRK.B"
    assert normalize_symbol("7203", "jp") == "7203.T"
    assert normalize_symbol("3.T", "jp") == "0003.T"


def test_unknown_market_rejected() -> None:
    with pytest.raises(ValueError):
        get_market_config("hk")
