from typing import List, Optional

from bankpromos.cache import is_fuel_cache_fresh, is_promotion_cache_fresh
from bankpromos.config import config
from bankpromos.core.deduper import dedupe_promotions
from bankpromos.core.models import FuelPriceModel, PromotionModel
from bankpromos.core.normalizer import normalize_promotion
from bankpromos.core.scoring import score_promotion
from bankpromos.fuel_prices import get_fuel_prices
from bankpromos.run_all import run_all_scrapers, run_scraper
from bankpromos.storage import (
    clear_fuel_prices,
    clear_promotions,
    init_db,
    load_fuel_prices,
    load_promotions,
    save_fuel_prices,
    save_promotions,
)


def _process_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []

    normalized = [normalize_promotion(p) for p in promos]
    deduped = dedupe_promotions(normalized)
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

    if not force_refresh and is_promotion_cache_fresh(max_age_hours=max_cache_age, db_path=db_path):
        cached = load_promotions(db_path)
        if cached:
            return cached

    all_promos: List[PromotionModel] = []
    _, errors = run_all_scrapers()

    for bank_id in ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]:
        try:
            promos, error = run_scraper(bank_id)
            if not error and promos:
                all_promos.extend(promos)
        except Exception:
            continue

    if not all_promos:
        cached = load_promotions(db_path)
        return cached

    processed = _process_promotions(all_promos)

    save_promotions(processed, db_path)

    return processed


def get_fuel_data(
    force_refresh: bool = False,
    db_path: str = DEFAULT_DB,
    max_cache_age: int = 12,
) -> List[FuelPriceModel]:
    init_db(db_path)

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
    init_db(db_path)

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