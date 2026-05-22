"""Scoring Tool   (KIK-708).

tools/  API 
src/data/scoring.py  re-export
"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.scoring import (  # noqa: E402
    score_return,
    score_growth,
    score_durability,
    score_quality,
    score_portfolio,
)

__all__ = [
    "score_return",
    "score_growth",
    "score_durability",
    "score_quality",
    "score_portfolio",
]
