"""Notes Tool  lesson .

tools/ 
src/data/note_manager  re-export
JSON  masterNeo4j  viewdual-write
"""

import sys
from pathlib import Path

#  sys.path 
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.note_manager import (  # noqa: E402
    save_note,
    load_notes,
    delete_note,
    get_exit_rules,
    check_exit_rule,
    check_lesson_conflicts,
)

__all__ = [
    "save_note",
    "load_notes",
    "delete_note",
    "get_exit_rules",
    "check_exit_rule",
    "check_lesson_conflicts",
]
