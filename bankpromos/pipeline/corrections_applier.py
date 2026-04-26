import logging
from typing import List, Optional

from bankpromos.collectors.base import Promotion
from bankpromos.corrections_service import (
    find_matching_correction,
    get_correction_by_key,
    list_corrections,
)

logger = logging.getLogger(__name__)


def mark_needs_review(promo: Promotion, reason: str) -> Promotion:
    if not promo.needs_review:
        promo.needs_review = True
        promo.review_reason = reason
    elif promo.review_reason:
        promo.review_reason = f"{promo.review_reason}; {reason}"
    return promo


def _should_mark_review(promo: Promotion) -> Optional[str]:
    if not promo.merchant_name or promo.merchant_name.strip() == "":
        if promo.category == "General":
            return "missing merchant + general category"
        return "missing merchant"

    merchant_lower = promo.merchant_name.lower().strip()
    if merchant_lower in ("none", "null", ""):
        return "null merchant"

    generic_merchant_patterns = {
        "reintegro del", "un descuento del", "beneficio del",
        "los meses con", "disfrut", "reintegro adicional del",
    }
    for pattern in generic_merchant_patterns:
        if pattern in merchant_lower:
            return f"generic merchant pattern: {pattern}"

    bank_names = {"ueno", "itau", "sudameris", "continental", "bnf", "banco"}
    if merchant_lower in bank_names:
        return "bank name used as merchant"

    if promo.category == "General" and not promo.merchant_name:
        return "general category without merchant"

    return None


def apply_needs_review_flag(promos: List[Promotion]) -> List[Promotion]:
    for promo in promos:
        reason = _should_mark_review(promo)
        if reason:
            mark_needs_review(promo, reason)
    return promos


def _apply_correction_to_promo(promo: Promotion, correction: dict) -> Promotion:
    if correction.get("corrected_merchant_name"):
        promo.merchant_name = correction["corrected_merchant_name"]

    if correction.get("corrected_category"):
        promo.category = correction["corrected_category"]

    if correction.get("corrected_discount_percent") is not None:
        from decimal import Decimal
        promo.discount_percent = Decimal(str(correction["corrected_discount_percent"]))

    if correction.get("corrected_installment_count") is not None:
        promo.installment_count = correction["corrected_installment_count"]

    if correction.get("corrected_cap_amount") is not None:
        from decimal import Decimal
        promo.cap_amount = Decimal(str(correction["corrected_cap_amount"]))

    if correction.get("corrected_valid_days"):
        promo.valid_days = correction["corrected_valid_days"]

    if correction.get("corrected_payment_method"):
        promo.payment_method = correction["corrected_payment_method"]

    promo.metadata = dict(promo.metadata)
    promo.metadata["corrected_from"] = correction.get("id")
    promo.metadata["correction_applied"] = True

    return promo


def apply_corrections(promos: List[Promotion], corrections: Optional[List[dict]] = None) -> tuple[List[Promotion], int]:
    if corrections is None:
        corrections = list_corrections(apply_to_future=True)

    applied_count = 0

    for promo in promos:
        correction = None

        if promo.pattern_key:
            correction = get_correction_by_key(promo.pattern_key)

        if not correction:
            correction = find_matching_correction(
                promo.bank_id,
                promo.raw_text or "",
                promo.merchant_name,
            )

        if correction and correction.get("apply_to_future", False):
            _apply_correction_to_promo(promo, correction)
            applied_count += 1
            logger.debug(f"[CORRECTIONS] Applied correction {correction['id']} to {promo.title[:50]}")
            continue

        reason = _should_mark_review(promo)
        if reason:
            mark_needs_review(promo, reason)

    return promos, applied_count


def get_review_items(promos: List[Promotion]) -> List[dict]:
    items = []
    for promo in promos:
        if promo.needs_review:
            items.append({
                "pattern_key": promo.pattern_key or "",
                "bank": promo.bank_id,
                "source_file": promo.source_url or "",
                "page": promo.metadata.get("page", 0),
                "detected_text": promo.raw_text or "",
                "detected_merchant": promo.merchant_name or "",
                "detected_discount": float(promo.discount_percent) if promo.discount_percent else None,
                "detected_category": promo.category or "",
                "detected_cap": float(promo.cap_amount) if promo.cap_amount else None,
                "detected_installments": promo.installment_count,
                "detected_days": promo.valid_days,
                "detected_payment_method": promo.payment_method,
                "detected_conditions": promo.metadata.get("conditions_text"),
                "reason": promo.review_reason or "",
                "crop_path": promo.metadata.get("crop_path"),
            })
    return items