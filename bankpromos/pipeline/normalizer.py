import logging
from typing import List

from bankpromos.collectors.base import Promotion
from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import normalize_promotion as core_normalize

logger = logging.getLogger(__name__)


def normalize_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []
    
    normalized = []
    for p in promos:
        try:
            norm = core_normalize(p)
            normalized.append(norm)
        except Exception as e:
            logger.warning(f"Normalize error: {e}, keeping original")
            normalized.append(p)
    
    logger.info(f"Normalized: {len(promos)} -> {len(normalized)}")
    return normalized


def normalize_raw(promos: List[Promotion]) -> List[Promotion]:
    """Normalize collector Promotion objects using legacy logic."""
    if not promos:
        return []
    
    legacy_promos = [_to_legacy(p) for p in promos]
    normalized = normalize_promotions(legacy_promos)
    
    return [_to_collector(p) for p in normalized]


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
    )