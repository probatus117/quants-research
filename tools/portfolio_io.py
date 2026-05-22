"""Portfolio I/O Tool  PF CSV .

tools/ 
src/data/portfolio_io  re-export
"""

import sys
from pathlib import Path

#  sys.path 
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.portfolio_io import (  # noqa: E402
    load_portfolio,
    save_portfolio,
    add_position,
    sell_position,
    update_next_earnings,
    get_performance_review,
    DEFAULT_CSV_PATH,
    # KIK-734: PF+ SSoT
    load_cash_balance,
    load_total_assets,
    DEFAULT_CASH_PATH,
)

__all__ = [
    "load_portfolio",
    "save_portfolio",
    "add_position",
    "sell_position",
    "update_next_earnings",
    "get_performance_review",
    "DEFAULT_CSV_PATH",
    # KIK-734
    "load_cash_balance",
    "load_total_assets",
    "DEFAULT_CASH_PATH",
]
