"""Grok API Tool  Grok (xAI) .

tools/  API 
src/data/grok_client/  re-export
XAI_API_KEY  graceful degradation
"""

import sys
from pathlib import Path

#  sys.path 
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.data.grok_client import (  # noqa: E402
        # 
        is_available,
        get_error_status,
        # symbol
        search_stock_deep,
        search_x_sentiment,
        # 
        search_market,
        search_trending_stocks,
        get_trending_themes,
        # 
        search_industry,
        # 
        search_business,
        # 
        synthesize_text,
    )
    # KIK-732: bulk search  wrapper (DeepThink Step 3 )
    from src.data.grok_client.bulk_search import (  # noqa: E402
        bulk_x_search,
        bulk_web_search,
    )
    HAS_GROK = True
except ImportError:
    HAS_GROK = False

__all__ = [
    # 
    "is_available",
    "get_error_status",
    # symbol
    "search_stock_deep",
    "search_x_sentiment",
    # 
    "search_market",
    "search_trending_stocks",
    "get_trending_themes",
    # 
    "search_industry",
    # 
    "search_business",
    # 
    "synthesize_text",
    # KIK-732: bulk 
    "bulk_x_search",
    "bulk_web_search",
    # 
    "HAS_GROK",
]
