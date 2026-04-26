import logging
from typing import List

from bankpromos.collectors.base import Promotion
from bankpromos.core.models import PromotionModel
from bankpromos.core.scoring import (
    calculate_quality_score as core_score,
    get_quality_label as core_label,
    score_promotion as core_score_promo,
)

logger = logging.getLogger(__name__)


def score_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []
    
    scored = []
    for p in promos:
        try:
            s = core_score_promo(p)
            scored.append(s)
        except Exception as e:
            logger.warning(f"Score error: {e}")
            p.result_quality_label = "LOW"
            p.result_quality_score = 0.0
            scored.append(p)
    
    high = sum(1 for p in scored if p.result_quality_label == "HIGH")
    logger.info(f"Scored: {len(promos)} (HIGH: {high})")
    return scored


def score_raw(promos: List[Promotion]) -> List[Promotion]:
    """Score collector Promotion objects using legacy logic."""
    if not promos:
        return []
    
    legacy_promos = [_to_legacy(p) for p in promos]
    scored = score_promotions(legacy_promos)
    
    return [_to_collector(p, s) for p, s in zip(promos, scored)]


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


def _to_collector(promo: Promotion, scored: PromotionModel) -> Promotion:
    promo.metadata = promo.metadata or {}
    promo.metadata["result_quality_score"] = scored.result_quality_score
    promo.metadata["result_quality_label"] = scored.result_quality_label
    return promo