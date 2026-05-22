"""GraphRAG Tool  Neo4j  .

tools/ 
src/data/graph_store/  src/data/graph_query/  re-export
Neo4j  graceful degradation
"""

import sys
from pathlib import Path

#  sys.path 
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ---  (graph_query) ---
try:
    from src.data.graph_query import (  # noqa: E402
        get_prior_report,
        get_screening_frequency,
        get_trade_context,
        get_report_trend,
        get_research_chain,
        get_stock_news_history,
        get_sentiment_trend,
        get_catalysts,
        get_current_holdings,
        get_holdings_notes,
        get_stress_test_history,
        get_forecast_history,
        get_recent_market_context,
        get_upcoming_events,
        get_theme_trends,
        get_communities,
        get_stock_community,
        get_community_lessons,
    )
    HAS_GRAPH_QUERY = True
except ImportError:
    HAS_GRAPH_QUERY = False

# ---  (graph_store) ---
try:
    from src.data.graph_store import (  # noqa: E402
        get_stock_history,
        merge_note,
        merge_trade,
        merge_report,
        merge_screen,
        get_open_action_items,
    )
    HAS_GRAPH_STORE = True
except ImportError:
    HAS_GRAPH_STORE = False

# ---  (auto_context) ---
try:
    from src.data.context import get_context  # noqa: E402
    HAS_CONTEXT = True
except ImportError:
    HAS_CONTEXT = False

# ---  (KIK-712) ---


def sync_all() -> dict:
    """data/  GraphRAG .

    SKILL.md sync
    Neo4j 

    Returns
    -------
    dict
        {"synced": [...], "failed": [...], "skipped": [...]}
    """
    import json
    import glob
    from datetime import datetime

    result = {"synced": [], "failed": [], "skipped": []}

    # Neo4j 
    try:
        from src.data.graph_store._common import is_available
        if not is_available():
            return {"synced": [], "failed": [], "skipped": ["Neo4j"]}
    except ImportError:
        return {"synced": [], "failed": [], "skipped": ["graph_store"]}

    # 1. Portfolio sync
    try:
        from src.data.portfolio_io import load_portfolio, DEFAULT_CSV_PATH
        from src.data.graph_store.portfolio import sync_portfolio
        holdings = load_portfolio(DEFAULT_CSV_PATH)
        if holdings:
            sync_portfolio(holdings)
            result["synced"].append(f"portfolio({len(holdings)}symbol)")
    except Exception as e:
        result["failed"].append(f"portfolio: {e}")

    # 2. Notes sync (data/notes/*.json)
    try:
        from src.data.graph_store.note import merge_note as _merge_note
        notes_dir = Path(_project_root) / "data" / "notes"
        if notes_dir.exists():
            note_files = sorted(notes_dir.glob("*.json"))
            synced_count = 0
            for nf in note_files:
                try:
                    with open(nf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # note_manager saves as list [{...}], handle both formats
                    note = data[0] if isinstance(data, list) else data
                    if not note:
                        continue
                    _merge_note(
                        note_id=note.get("id", nf.stem),
                        note_date=note.get("date", ""),
                        note_type=note.get("type", "observation"),
                        content=note.get("content", ""),
                        symbol=note.get("symbol"),
                        source=note.get("source", "claude"),
                        category=note.get("category", ""),
                    )
                    synced_count += 1
                except Exception:
                    result["failed"].append(f"note: {nf.name}")
            if synced_count:
                result["synced"].append(f"notes({synced_count})")
    except Exception as e:
        result["failed"].append(f"notes: {e}")

    # 3. Update sync_status.yaml
    try:
        status_path = Path(_project_root) / "data" / "sync_status.yaml"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        status = {"last_sync": datetime.now().isoformat()}
        with open(status_path, "w", encoding="utf-8") as f:
            yaml.dump(status, f)
        result["synced"].append("sync_status")
    except Exception:
        pass  # non-critical

    return result


__all__ = [
    # 
    "get_prior_report",
    "get_screening_frequency",
    "get_trade_context",
    "get_report_trend",
    "get_research_chain",
    "get_stock_news_history",
    "get_sentiment_trend",
    "get_catalysts",
    "get_current_holdings",
    "get_holdings_notes",
    "get_stress_test_history",
    "get_forecast_history",
    "get_recent_market_context",
    "get_upcoming_events",
    "get_theme_trends",
    "get_communities",
    "get_stock_community",
    "get_community_lessons",
    # 
    "get_stock_history",
    "merge_note",
    "merge_trade",
    "merge_report",
    "merge_screen",
    "get_open_action_items",
    # 
    "get_context",
    # 
    "sync_all",
    # 
    "HAS_GRAPH_QUERY",
    "HAS_GRAPH_STORE",
    "HAS_CONTEXT",
]
