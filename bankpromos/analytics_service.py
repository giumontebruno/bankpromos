import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

ANALYTICS_PATH = Path("data/analytics_events.jsonl")


def _get_today() -> str:
    return date.today().isoformat()


def _ensure_analytics_dir():
    ANALYTICS_PATH.parent.mkdir(parents=True, exist_ok=True)


def track_event(
    event_type: str,
    query: Optional[str] = None,
    category: Optional[str] = None,
    bank: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> bool:
    try:
        _ensure_analytics_dir()
        event = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "query": query[:100] if query else None,
            "category": category,
            "bank": bank,
            "metadata": metadata or {},
        }
        with open(ANALYTICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.warning(f"Failed to track event: {e}")
        return False


def _load_events(limit: int = 1000) -> List[Dict[str, Any]]:
    events = []
    if not ANALYTICS_PATH.exists():
        return events
    try:
        with open(ANALYTICS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events[-limit:]
    except Exception:
        return events


def get_event_counts(event_type: Optional[str] = None) -> Dict[str, int]:
    events = _load_events(limit=10000)
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    counts = Counter(e.get("event_type") for e in events)
    return dict(counts)


def get_today_summary() -> Dict[str, Any]:
    today = _get_today()
    events = _load_events(limit=5000)
    today_events = [e for e in events if e.get("timestamp", "").startswith(today)]
    
    event_counts = Counter(e.get("event_type") for e in today_events)
    
    queries = [e.get("query") for e in today_events if e.get("query")]
    top_searches = Counter(queries).most_common(5)
    
    categories = [e.get("category") for e in today_events if e.get("category")]
    top_cats = Counter(categories).most_common(5)
    
    return {
        "date": today,
        "total_events": len(today_events),
        "searches": event_counts.get("search_query", 0),
        "fuel_searches": event_counts.get("fuel_query", 0),
        "today_views": event_counts.get("today_view", 0),
        "personalized_views": event_counts.get("today_personalized_view", 0),
        "preferences_saved": event_counts.get("preference_save", 0),
        "top_queries": [{"query": q, "count": c} for q, c in top_searches if q],
        "top_categories": [{"category": c, "count": ct} for c, ct in top_cats if c],
    }


def get_top_queries(limit: int = 10) -> List[Dict[str, Any]]:
    events = _load_events(limit=5000)
    queries = [e.get("query") for e in events if e.get("query")]
    counts = Counter(queries)
    return [
        {"query": q, "count": c}
        for q, c in counts.most_common(limit)
        if q
    ]


def get_top_categories(limit: int = 10) -> List[Dict[str, Any]]:
    events = _load_events(limit=5000)
    cats = [e.get("category") for e in events if e.get("category")]
    counts = Counter(cats)
    return [
        {"category": c, "count": ct}
        for c, ct in counts.most_common(limit)
        if c
    ]


def get_analytics_summary() -> Dict[str, Any]:
    events = _load_events(limit=10000)
    total = len(events)
    
    event_counts = Counter(e.get("event_type") for e in events)
    unique_queries = len(set(e.get("query") for e in events if e.get("query")))
    unique_cats = len(set(e.get("category") for e in events if e.get("category")))
    
    return {
        "total_events": total,
        "unique_queries": unique_queries,
        "unique_categories": unique_cats,
        "by_type": dict(event_counts),
    }