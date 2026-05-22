"""Tests for src.data.ticker_utils (KIK-473, KIK-597)."""

import pytest

from src.data.ticker_utils import (
    extract_all_symbols,
    round_to_lot_size,
    validate_lot_size,
)


class TestExtractAllSymbols:
    def test_single_symbol(self):
        result = extract_all_symbols("NVDA急騰已执行")
        assert result == ["NVDA"]

    def test_multiple_symbols(self):
        result = extract_all_symbols("NVDA和AAPL上。7203.T下落")
        assert set(result) == {"NVDA", "AAPL", "7203.T"}

    def test_no_symbols(self):
        result = extract_all_symbols("今日交易不执行")
        assert result == []

    def test_duplicate_removal(self):
        result = extract_all_symbols("NVDA上。NVDA的決算也良")
        assert result == ["NVDA"]

    def test_suffix_symbols(self):
        result = extract_all_symbols("D05.SI和SINT.SI買")
        assert set(result) == {"D05.SI", "SINT.SI"}

    def test_empty_string(self):
        result = extract_all_symbols("")
        assert result == []


# ===================================================================
# round_to_lot_size tests (KIK-597)
# ===================================================================


class TestRoundToLotSize:
    def test_jp_stock_rounds_down(self):
        assert round_to_lot_size(149, "7203.T") == 100

    def test_jp_stock_rounds_up(self):
        assert round_to_lot_size(151, "7203.T") == 200

    def test_jp_stock_exact_multiple(self):
        assert round_to_lot_size(300, "7203.T") == 300

    def test_jp_stock_midpoint(self):
        # Python banker's rounding: 150/100=1.5 → 2
        assert round_to_lot_size(150, "7203.T") == 200

    def test_us_stock_passthrough(self):
        assert round_to_lot_size(17, "AAPL") == 17

    def test_taiwan_stock_lot_1000(self):
        assert round_to_lot_size(1499, "2330.TW") == 1000

    def test_zero_shares(self):
        assert round_to_lot_size(0, "7203.T") == 0

    def test_below_half_lot(self):
        assert round_to_lot_size(49, "7203.T") == 0

    def test_sg_stock_100_lot(self):
        assert round_to_lot_size(150, "D05.SI") == 200

    def test_cash_symbol(self):
        assert round_to_lot_size(50, "JPY.CASH") == 50


# ===================================================================
# validate_lot_size tests (KIK-597)
# ===================================================================


class TestValidateLotSize:
    def test_valid_jp_stock(self):
        validate_lot_size(100, "7203.T")
        validate_lot_size(200, "7203.T")

    def test_invalid_jp_stock_raises(self):
        with pytest.raises(ValueError, match="100 股为单位"):
            validate_lot_size(50, "7203.T")

    def test_error_message_includes_nearest(self):
        with pytest.raises(ValueError, match="最接近的有效股数: 200 股"):
            validate_lot_size(150, "7203.T")

    def test_us_stock_any_amount_passes(self):
        validate_lot_size(1, "AAPL")
        validate_lot_size(7, "MSFT")

    def test_taiwan_stock_1000_lot(self):
        with pytest.raises(ValueError, match="1000 股为单位"):
            validate_lot_size(500, "2330.TW")

    def test_sg_stock_100_lot(self):
        with pytest.raises(ValueError, match="100 股为单位"):
            validate_lot_size(22, "D05.SI")

    def test_cash_symbol_passes(self):
        validate_lot_size(50, "JPY.CASH")
