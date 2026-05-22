"""Preflight Tool  DeepThink  gate (KIK-735).

tools/  API 
src/data/preflight  re-export
"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.preflight import (  # noqa: E402
    PreflightError,
    run_preflight,
    extract_convictions,
)

__all__ = [
    "PreflightError",
    "run_preflight",
    "extract_convictions",
]
