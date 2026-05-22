"""Cash Balance Tool  KIK-742 SSoT.

tools/ 
data/cash_balance.json 

# Cash Balance Schema (SSoT)

KIK-742 :

```json
{
  "date": "YYYY-MM-DD",
  "timestamp": "ISO-8601",
  "total_jpy": 1234567,
  "breakdown": {
    "USD": {"amount": 5934.21, "jpy_equivalent": 947634, "rate_jpy_per_usd": 159.69},
    "JPY": {"amount": 233969}
  },
  "changelog": ["..."]
}
```

`session_state.py`  `src/data/portfolio_io.py:load_cash_balance` 
"""

import json
import os
from datetime import datetime
from pathlib import Path

_CASH_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "cash_balance.json"
)


def load_cash_balance(path: str = _CASH_PATH) -> dict:
    """KIK-742.

    Returns
    -------
    dict
        {"date": str, "total_jpy": float, "breakdown": {...}, ...}
         dict
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cash_balance(balances: dict, path: str = _CASH_PATH) -> None:
    """KIK-742.

    Parameters
    ----------
    balances : dict
        module docstring 
        date / timestamp 

    Notes
    -----
    {"JPY": 1234, "USD": 5.6}
     JSON load_cash_balance() 
    """
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    balances.setdefault("date", now.strftime("%Y-%m-%d"))
    balances["timestamp"] = now.isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(balances, f, indent=2, ensure_ascii=False)


def update_currency(
    currency: str,
    amount: float,
    path: str = _CASH_PATH,
    *,
    jpy_equivalent: float | None = None,
    rate_jpy_per_usd: float | None = None,
) -> dict:
    """KIK-742.

    Parameters
    ----------
    currency : str
        code"JPY", "USD" 
    amount : float
        
    jpy_equivalent : float, optional
        JPY USD
    rate_jpy_per_usd : float, optional
        USD
    """
    balances = load_cash_balance(path)
    balances.setdefault("breakdown", {})
    entry: dict = {"amount": amount}
    if jpy_equivalent is not None:
        entry["jpy_equivalent"] = jpy_equivalent
    if rate_jpy_per_usd is not None:
        entry["rate_jpy_per_usd"] = rate_jpy_per_usd
    balances["breakdown"][currency.upper()] = entry
    # total_jpy 
    save_cash_balance(balances, path)
    return balances


__all__ = [
    "load_cash_balance",
    "save_cash_balance",
    "update_currency",
]
