import logging
from typing import List, Optional, Dict, Any

DEFAULT_DB = "bankpromos.db"

from bankpromos.cache import is_fuel_cache_fresh, is_promotion_cache_fresh
from bankpromos.config import config
from bankpromos.core.deduper import dedupe_promotions
from bankpromos.core.models import FuelPriceModel, PromotionModel
from bankpromos.core.normalizer import normalize_promotion, _is_weak_promotion
from bankpromos.core.scoring import score_promotion
from bankpromos.fuel_prices import get_fuel_prices
from bankpromos.run_all import run_all_scrapers, run_scraper
from bankpromos.scrapers.base_public import ScraperDiagnostics
from bankpromos.storage import (
    clear_fuel_prices,
    clear_promotions,
    init_db,
    load_fuel_prices,
    load_promotions,
    save_fuel_prices,
    save_promotions,
)

logger = logging.getLogger(__name__)


def _filter_weak_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    return [p for p in promos if not _is_weak_promotion(p)]


def _process_promotions(promos: List[PromotionModel], bank_id: str = "unknown") -> List[PromotionModel]:
    if not promos:
        return []

    normalized = [normalize_promotion(p) for p in promos]
    filtered = _filter_weak_promotions(normalized)

    total = len(promos)
    after_norm = len(normalized)
    after_filter = len(filtered)

    dropped = total - after_filter
    if dropped > 0:
        logger.info(f"[{bank_id}] Filtered {dropped} weak promotions ({total} scraped → {after_filter} saved)")

    deduped = dedupe_promotions(filtered)
    scored = [score_promotion(p) for p in deduped]

    return scored


def get_promotions_data(
    force_refresh: bool = False,
    db_path: str = None,
    max_cache_age: int = 12,
) -> List[PromotionModel]:
    if db_path is None:
        db_path = config.db_path
    init_db(db_path)

    if config.disable_live_scraping:
        logger.info("Live scraping disabled, loading from cache only")
        cached = load_promotions(db_path)
        if cached:
            return cached
        return []

    if not force_refresh and is_promotion_cache_fresh(max_age_hours=max_cache_age, db_path=db_path):
        cached = load_promotions(db_path)
        if cached:
            return cached

    all_promos: List[PromotionModel] = []
    bank_ids = ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]

    for bank_id in bank_ids:
        try:
            promos, error = run_scraper(bank_id)
            if not error and promos:
                processed_bank = _process_promotions(promos, bank_id)
                all_promos.extend(processed_bank)
        except Exception:
            continue

    if not all_promos:
        cached = load_promotions(db_path)
        return cached

    save_promotions(all_promos, db_path)

    return all_promos


def get_fuel_data(
    force_refresh: bool = False,
    db_path: str = DEFAULT_DB,
    max_cache_age: int = 12,
) -> List[FuelPriceModel]:
    init_db(db_path)

    if config.disable_live_scraping:
        logger.info("Live scraping disabled, loading fuel data from cache only")
        cached = load_fuel_prices(db_path)
        if cached:
            return cached
        return []

    if not force_refresh and is_fuel_cache_fresh(max_age_hours=max_cache_age, db_path=db_path):
        cached = load_fuel_prices(db_path)
        if cached:
            return cached

    prices = get_fuel_prices()

    if not prices:
        cached = load_fuel_prices(db_path)
        return cached

    save_fuel_prices(prices, db_path)

    return prices


def collect_all_data(
    force_refresh: bool = False,
    db_path: str = DEFAULT_DB,
) -> dict:
    if db_path is None:
        db_path = config.db_path

    init_db(db_path)

    if config.disable_live_scraping:
        logger.info("Live scraping disabled, loading from existing database")
        promos = load_promotions(db_path)
        fuel_prices = load_fuel_prices(db_path)
        return {
            "promotions_count": len(promos) if promos else 0,
            "fuel_prices_count": len(fuel_prices) if fuel_prices else 0,
            "promos_updated": get_last_promotion_timestamp(db_path),
            "fuel_updated": get_last_fuel_timestamp(db_path),
            "note": "Live scraping disabled - serving cached data only",
        }

    if force_refresh:
        clear_promotions(db_path)
        clear_fuel_prices(db_path)

    promos = get_promotions_data(force_refresh=force_refresh, db_path=db_path)
    fuel_prices = get_fuel_data(force_refresh=force_refresh, db_path=db_path)

    return {
        "promotions_count": len(promos),
        "fuel_prices_count": len(fuel_prices),
        "promos_updated": get_last_promotion_timestamp(db_path),
        "fuel_updated": get_last_fuel_timestamp(db_path),
    }


def collect_debug_data(
    force_refresh: bool = False,
    db_path: str = DEFAULT_DB,
) -> Dict[str, Any]:
    if db_path is None:
        db_path = config.db_path

    if config.disable_live_scraping:
        return {
            "total_promotions": 0,
            "bank_count": 0,
            "diagnostics": [],
            "note": "Live scraping disabled",
        }

    from bankpromos.run_all import run_scraper_with_diagnostics

    init_db(db_path)

    if force_refresh:
        clear_promotions(db_path)
        clear_fuel_prices(db_path)

    bank_ids = ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]
    diagnostics: List[Dict[str, Any]] = []

    for bank_id in bank_ids:
        logger.info(f"Running debug scraper: {bank_id}")
        promos, diag, error = run_scraper_with_diagnostics(bank_id, debug_mode=True)
        if diag:
            diagnostics.append(diag.to_dict())
        else:
            diagnostics.append({
                "bank_id": bank_id,
                "success": False,
                "url": "",
                "title": "",
                "body_text_length": 0,
                "card_matches": 0,
                "pdf_links_found": 0,
                "fallback_ran": False,
                "extracted_before_dedupe": 0,
                "extracted_after_dedupe": 0,
                "error": error or "Unknown error",
            })

    all_promos = [d["extracted_after_dedupe"] for d in diagnostics if d.get("success")]
    total_promos = sum(all_promos)

    return {
        "total_promotions": total_promos,
        "bank_count": len(bank_ids),
        "diagnostics": diagnostics,
    }


def get_last_promotion_timestamp(db_path: str = DEFAULT_DB) -> Optional[str]:
    from bankpromos.storage import get_last_promotion_update

    update = get_last_promotion_update(db_path)
    if update:
        return update.isoformat()
    return None


def get_last_fuel_timestamp(db_path: str = DEFAULT_DB) -> Optional[str]:
    from bankpromos.storage import get_last_fuel_update

    update = get_last_fuel_update(db_path)
    if update:
        return update.isoformat()
    return None


def clear_all_data(db_path: str = DEFAULT_DB) -> None:
    clear_promotions(db_path)
    clear_fuel_prices(db_path)