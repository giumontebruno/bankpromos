import logging
from typing import List

from bankpromos.collectors.base import Promotion
from bankpromos.core.models import PromotionModel
from bankpromos.core.deduper import dedupe_promotions as core_dedupe

logger = logging.getLogger(__name__)


def deduplicate_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []
    
    try:
        deduped = core_dedupe(promos)
        logger.info(f"Deduped: {len(promos)} -> {len(deduped)}")
        return deduped
    except Exception as e:
        logger.warning(f"Dedupe error: {e}, returning original")
        return promos


def deduplicate_raw(promos: List[Promotion]) -> List[Promotion]:
    """Deduplicate collector Promotion objects using legacy logic."""
    if not promos:
        return []
    
    legacy_promos = [_to_legacy(p) for p in promos]
    deduped = deduplicate_promotions(legacy_promos)
    
    return [_to_collector(p) for p in deduped]


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
        raw_data=dict(promo.metadata) if promo.metadata else {},
        needs_review=promo.needs_review,
        review_reason=promo.review_reason,
        pattern_key=promo.pattern_key,
    )


def _to_collector(promo: PromotionModel) -> Promotion:
    return Promotion(
        bank_id=promo.bank_id,
        title=promo.title,
        merchant_name=promo.merchant_name,
        category=promo.category,
        benefit_type=promo.benefit_type,
        discount_percent=promo.discount_percent,
        installment_count=promo.installment_count,
        valid_days=promo.valid_days or [],
        valid_from=promo.valid_from,
        valid_to=promo.valid_to,
        cap_amount=promo.cap_amount,
        payment_method=promo.payment_method,
        source_url=promo.source_url or "",
        raw_text=promo.raw_text,
        metadata=promo.raw_data or {},
        needs_review=promo.needs_review,
        review_reason=promo.review_reason,
        pattern_key=promo.pattern_key,
    )