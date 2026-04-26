import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from bankpromos.storage import load_promotions

logger = logging.getLogger(__name__)


@dataclass
class CollectionSummary:
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_promos: int = 0
    total_fuel_prices: int = 0
    curated_count: int = 0
    scraped_count: int = 0
    active_today_count: int = 0
    promos_by_bank: Dict[str, int] = field(default_factory=dict)
    promos_by_category: Dict[str, int] = field(default_factory=dict)
    fuel_by_emblem: Dict[str, int] = field(default_factory=dict)
    top_categories: List[str] = field(default_factory=list)
    new_promos: int = 0
    removed_promos: int = 0
    changed_promos: int = 0


def load_promos_from_db(db_path: str = "bankpromos.db") -> List[Any]:
    try:
        return load_promotions(db_path)
    except Exception as e:
        logger.warning(f"Could not load promos: {e}")
        return []


def load_fuel_from_db(db_path: str = "bankpromos.db") -> List[Any]:
    try:
        from bankpromos.storage import load_fuel_prices
        return load_fuel_prices(db_path)
    except Exception as e:
        logger.warning(f"Could not load fuel: {e}")
        return []


def generate_summary(db_path: str = "bankpromos.db", previous_summary: Optional[Dict] = None) -> CollectionSummary:
    promos = load_promos_from_db(db_path)
    fuel = load_fuel_from_db(db_path)

    summary = CollectionSummary()
    summary.total_promos = len(promos)

    curated = [p for p in promos if getattr(p, "result_quality_label", "") == "CURATED"]
    scraped = [p for p in promos if getattr(p, "result_quality_label", "") != "CURATED"]
    summary.curated_count = len(curated)
    summary.scraped_count = len(scraped)

    banks = {}
    categories = {}
    today = datetime.now().weekday()

    for p in promos:
        bank = p.bank_id or "unknown"
        banks[bank] = banks.get(bank, 0) + 1

        cat = p.category or "General"
        categories[cat] = categories.get(cat, 0) + 1

        valid_days = p.valid_days or []
        if not valid_days:
            summary.active_today_count += 1
        else:
            day_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
            valid_lower = [d.lower() for d in valid_days]
            if any(day_map.get(d, -1) == today for d in valid_lower):
                summary.active_today_count += 1

    summary.promos_by_bank = banks
    summary.promos_by_category = categories

    sorted_cats = sorted(categories.items(), key=lambda x: -x[1])
    summary.top_categories = [c for c, _ in sorted_cats[:5]]

    fuel_by_emblem = {}
    for f in fuel:
        emblem = getattr(f, "emblem", None) or "unknown"
        fuel_by_emblem[emblem] = fuel_by_emblem.get(emblem, 0) + 1
    summary.fuel_by_emblem = fuel_by_emblem
    summary.total_fuel_prices = len(fuel)

    if previous_summary:
        prev_total = previous_summary.get("total_promos", 0)
        summary.new_promos = max(0, summary.total_promos - prev_total)
        summary.removed_promos = max(0, prev_total - summary.total_promos)

    return summary


def save_summary(summary: CollectionSummary, path: str = "data/collection_summary.json") -> bool:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save summary: {e}")
        return False


def load_summary(path: str = "data/collection_summary.json") -> Optional[Dict]:
    try:
        if Path(path).exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def run_collection_with_summary(db_path: str = "bankpromos.db", save: bool = True) -> CollectionSummary:
    previous = load_summary()
    summary = generate_summary(db_path, previous)
    if save:
        save_summary(summary)
    return summary