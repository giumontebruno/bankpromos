import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bankpromos.collectors import get_collector, list_collectors
from bankpromos.collectors.base import Promotion, Source
from bankpromos.core.models import PromotionModel
from bankpromos.pipeline.corrections_applier import apply_corrections, apply_needs_review_flag
from bankpromos.pipeline.normalizer import normalize_raw
from bankpromos.pipeline.deduper import deduplicate_raw
from bankpromos.pipeline.scorer import score_raw
from bankpromos.pipeline.writer import write_to_db

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    bank_id: str
    sources_found: int = 0
    promos_collected: int = 0
    promos_normalized: int = 0
    promos_deduped: int = 0
    promos_saved: int = 0
    parser_mode: str = "classic"
    parser_used: str = "classic"
    errors: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


def run_bank_collection(
    bank_id: str,
    db_path: str = "bankpromos.db",
    debug: bool = False,
    parser_mode: str = "classic",
    clear_first: bool = False,
) -> CollectionResult:
    """Run full pipeline for a single bank."""
    result = CollectionResult(bank_id=bank_id, parser_mode=parser_mode)
    
    collector = get_collector(bank_id)
    if not collector:
        result.errors.append(f"No collector for {bank_id}")
        return result
    
    sources = collector.discover_sources()
    result.sources_found = len(sources)
    
    if debug:
        logger.info(f"{bank_id}: {len(sources)} sources (parser_mode: {parser_mode})")
    
    raw_promos = collector.collect(sources)
    result.promos_collected = len(raw_promos)
    
    raw_promos, corrections_applied = apply_corrections(raw_promos)
    result.metadata["corrections_applied"] = corrections_applied
    
    if debug:
        logger.info(f"{bank_id}: {len(raw_promos)} collected, {corrections_applied} corrections applied")
    
    if not raw_promos:
        return result
    
    normalized = normalize_raw(raw_promos)
    result.promos_normalized = len(normalized)
    
    if debug:
        logger.info(f"{bank_id}: {len(normalized)} normalized")
    
    deduped = deduplicate_raw(normalized)
    result.promos_deduped = len(deduped)
    
    if debug:
        logger.info(f"{bank_id}: {len(deduped)} deduped")
    
    scored = score_raw(deduped)
    
    if debug:
        logger.info(f"{bank_id}: {len(scored)} scored")
    
    legacy_promos = [_to_legacy(p) for p in scored]
    write_result = write_to_db(legacy_promos, db_path, clear_first=clear_first)
    result.promos_saved = write_result.get("written", 0)
    
    if debug:
        logger.info(f"{bank_id}: {result.promos_saved} saved to {db_path}")
    
    return result


def run_all_collections(
    db_path: str = "bankpromos.db",
    debug: bool = False,
    parser_mode: str = "classic",
    clear_first: bool = False,
) -> Dict[str, CollectionResult]:
    """Run full pipeline for all collectors."""
    results = {}
    
    for bank_id in list_collectors():
        try:
            result = run_bank_collection(bank_id, db_path, debug, parser_mode)
            results[bank_id] = result
        except Exception as e:
            logger.warning(f"Collection error for {bank_id}: {e}")
            results[bank_id] = CollectionResult(bank_id=bank_id, errors=[str(e)], parser_mode=parser_mode)
    
    return results


def _to_legacy(promo: Promotion) -> PromotionModel:
    return PromotionModel(
        bank_id=promo.bank_id,
        title=promo.title,
        merchant_name=promo.merchant_name,
        category=promo.category,
        benefit_type=promo.benefit_type,
        discount_percent=promo.discount_percent,
        installment_count=promo.installment_count,
        valid_days=promo.valid_days,
        valid_from=promo.valid_from,
        valid_to=promo.valid_to,
        cap_amount=promo.cap_amount,
        payment_method=promo.payment_method,
        source_url=promo.source_url or "",
        raw_text=promo.raw_text,
        raw_data=promo.metadata,
    )


def print_results(results: Dict[str, CollectionResult]) -> None:
    """Print collection results in a readable format."""
    total_saved = 0
    
    print("\nCollection Results:")
    print("-" * 60)
    print(f"{'Bank':<15} {'Sources':>8} {'Coll':>6} {'Norm':>6} {'Dedup':>6} {'Saved':>6}")
    print("-" * 60)
    
    for bank_id, r in results.items():
        print(
            f"{bank_id:<15} {r.sources_found:>8} {r.promos_collected:>6} "
            f"{r.promos_normalized:>6} {r.promos_deduped:>6} {r.promos_saved:>6}"
        )
        total_saved += r.promos_saved
    
    print("-" * 60)
    print(f"{'TOTAL':>15} {'':<8} {'':<6} {'':<6} {'':<6} {total_saved:>6}")
    print()