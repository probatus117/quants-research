"""Morning Summary Tool   (KIK-717).

tools/  API 
src/data/morning_summary.py  re-export
"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.morning_summary import (  # noqa: E402
    detect_alerts,
    format_morning_summary,
    ALERT_THRESHOLDS,
)

__all__ = [
    "detect_alerts",
    "format_morning_summary",
    "ALERT_THRESHOLDS",
]
