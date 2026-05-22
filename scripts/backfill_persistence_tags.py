"""Backfill `persistence` tag for existing lesson notes (KIK-739 Phase 1).

Each lesson is classified by Gemini into one of:
  - permanent:   lot sizePF balance normalconviction 
  - situational: NFLX CEG 
  - seasonal:    / 4% 
  - expired:     

Usage
-----
Dry-run (CSV report only):
    python3 scripts/backfill_persistence_tags.py --dry-run

Apply:
    python3 scripts/backfill_persistence_tags.py --execute

Limit (debug):
    python3 scripts/backfill_persistence_tags.py --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_PROJECT_ROOT / ".env")

from tools.llm import call_llm  # noqa: E402
from tools.notes import load_notes  # noqa: E402
from src.data.note_manager import update_lesson_metadata, _VALID_PERSISTENCE  # noqa: E402


_SYSTEM_PROMPT = """\
 lesson persistence lesson  content
 trigger / expected_action 4 


- permanent: 
   conviction lot PF balance 
       lesson
- situational: 
  NFLX  conviction CEG 
- seasonal: 
   4%  VIX  25 
- expired: 


-  situationalpermanent 
- expired  seasonal

 JSON
{"persistence": "permanent" | "situational" | "seasonal" | "expired", "reason": "1 "}
"""

_USER_TEMPLATE = """\
 lesson 

date: {date}
symbol: {symbol}
trigger: {trigger}
expected_action: {expected_action}
content ():
\"\"\"
{content}
\"\"\"
"""


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    payload = fence.group(1) if fence else text
    brace = re.search(r"\{.*\}", payload, re.S)
    if not brace:
        return None
    try:
        obj = json.loads(brace.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _classify(lesson: dict) -> dict | None:
    """Call Gemini to classify the persistence of a lesson."""
    prompt = _USER_TEMPLATE.format(
        date=lesson.get("date", "(unknown)"),
        symbol=lesson.get("symbol") or "(none)",
        trigger=(lesson.get("trigger") or "(none)")[:200],
        expected_action=(lesson.get("expected_action") or "(none)")[:200],
        content=(lesson.get("content") or "")[:1500],
    )
    raw = call_llm(
        provider="gemini",
        model="gemini-2.5-pro",
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        timeout=60,
    )
    if not raw:
        return None
    obj = _extract_json(raw)
    if not obj:
        return None
    persistence = (obj.get("persistence") or "").strip().lower()
    if persistence not in _VALID_PERSISTENCE:
        return None
    return {"persistence": persistence, "reason": (obj.get("reason") or "").strip()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill lesson persistence tags (KIK-739)")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true")
    grp.add_argument("--execute", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--csv-out", default="/tmp/persistence_backfill.csv",
        help="CSV report path (dry-run mode)",
    )
    p.add_argument(
        "--reclassify-all", action="store_true",
        help="Re-classify even lessons that already have a persistence tag",
    )
    args = p.parse_args(argv)

    lessons = load_notes(note_type="lesson")
    if args.reclassify_all:
        targets = lessons
    else:
        targets = [l for l in lessons if not l.get("persistence")]
    if args.limit:
        targets = targets[: args.limit]

    print(f"Total lessons: {len(lessons)}, target: {len(targets)}", file=sys.stderr)
    if not targets:
        print("Nothing to backfill.", file=sys.stderr)
        return 0

    rows: list[dict] = []
    applied = 0
    for i, lesson in enumerate(targets, 1):
        nid = lesson.get("id", "")
        date = lesson.get("date", "")
        print(f"[{i}/{len(targets)}] {date} {nid[:30]} ...", file=sys.stderr, end=" ", flush=True)
        cls = _classify(lesson)
        if cls is None:
            print("SKIP (classify failed)", file=sys.stderr)
            rows.append({
                "id": nid, "date": date, "persistence": "(failed)", "reason": "",
                "trigger": lesson.get("trigger", "")[:60],
            })
            continue
        rows.append({
            "id": nid, "date": date,
            "persistence": cls["persistence"], "reason": cls["reason"],
            "trigger": lesson.get("trigger", "")[:60],
        })
        if args.execute:
            updated = update_lesson_metadata(nid, persistence=cls["persistence"])
            if updated is None:
                print(f"WARN (update failed) - {cls['persistence']}", file=sys.stderr)
            else:
                applied += 1
                print(f"OK {cls['persistence']:<12} {cls['reason'][:40]}", file=sys.stderr)
        else:
            print(f"OK (dry) {cls['persistence']:<12} {cls['reason'][:40]}", file=sys.stderr)

    out_path = Path(args.csv_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "date", "persistence", "reason", "trigger"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV report: {out_path}", file=sys.stderr)

    # Distribution summary
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["persistence"]] = counts.get(r["persistence"], 0) + 1
    print(f"Distribution: {counts}", file=sys.stderr)

    if args.execute:
        print(f"Applied: {applied}/{len(targets)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
