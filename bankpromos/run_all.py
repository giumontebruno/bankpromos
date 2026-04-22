from typing import Dict, List, Optional, Tuple, Any

from bankpromos.core.deduper import dedupe_promotions
from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import normalize_promotion
from bankpromos.core.scoring import score_promotion
from bankpromos.scrapers import get_scraper
from bankpromos.scrapers.base_public import ScraperDiagnostics


SUPPORTED_BANKS = ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]


def run_scraper(bank_id: str, debug_mode: bool = False) -> Tuple[List[PromotionModel], Optional[str]]:
    if bank_id not in SUPPORTED_BANKS:
        return [], f"Unsupported bank: {bank_id}"

    try:
        scraper = get_scraper(bank_id, debug_mode=debug_mode)
        promos = scraper.scrape()
        return promos, None
    except Exception as e:
        return [], str(e)


def run_scraper_with_diagnostics(bank_id: str, debug_mode: bool = True) -> Tuple[List[PromotionModel], Optional[ScraperDiagnostics], Optional[str]]:
    if bank_id not in SUPPORTED_BANKS:
        return [], None, f"Unsupported bank: {bank_id}"

    try:
        scraper = get_scraper(bank_id, debug_mode=debug_mode)
        promos = scraper.scrape()
        diag = scraper.get_diagnostics()
        return promos, diag, None
    except Exception as e:
        return [], None, str(e)


def run_all_scrapers(
    bank_ids: Optional[List[str]] = None,
    debug_mode: bool = False,
) -> Tuple[List[PromotionModel], Dict[str, str]]:
    if bank_ids is None:
        bank_ids = SUPPORTED_BANKS

    bank_ids = [b for b in bank_ids if b in SUPPORTED_BANKS]
    if not bank_ids:
        bank_ids = SUPPORTED_BANKS

    all_promos: List[PromotionModel] = []
    errors: Dict[str, str] = {}

    for bank_id in bank_ids:
        print(f"Running scraper: {bank_id}")
        promos, error = run_scraper(bank_id, debug_mode=debug_mode)

        if error:
            print(f"  Error: {error}")
            errors[bank_id] = error
        else:
            print(f"  Found {len(promos)} promotions")
            all_promos.extend(promos)

    if not all_promos:
        return [], errors

    print(f"\nNormalizing {len(all_promos)} promotions...")
    normalized = [normalize_promotion(p) for p in all_promos]

    print(f"Deduplicating...")
    deduped = dedupe_promotions(normalized)

    print(f"Scoring...")
    scored = [score_promotion(p) for p in deduped]

    print(f"\nFinal: {len(scored)} unique promotions")
    return scored, errors