import unicodedata
from typing import List, Optional

from bankpromos.core.models import PromotionModel


def _normalize_for_compare(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    text = text.replace("ñ", "n")
    text = "".join(c for c in text if c.isalnum() or c.isspace())
    return text.strip()


def _merchants_match(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False

    na = _normalize_for_compare(a)
    nb = _normalize_for_compare(b)

    if not na or not nb:
        return False

    if na == nb:
        return True

    words_a = set(na.split())
    words_b = set(nb.split())

    if not words_a or not words_b:
        return False

    intersection = words_a & words_b
    union = words_a | words_b

    jaccard = len(intersection) / len(union) if union else 0

    if jaccard >= 0.5:
        return True

    if len(na) > 3 and len(nb) > 3:
        if na.startswith(nb[:4]) or nb.startswith(na[:4]):
            return True

    return False


def _benefits_match(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return True

    return a.lower().strip() == b.lower().strip()


def _discounts_match(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return True
    return abs(a - b) < 0.01


def _cuotas_match(a: Optional[int], b: Optional[int]) -> bool:
    if a is None or b is None:
        return True
    return a == b


def _is_duplicate(p1: PromotionModel, p2: PromotionModel) -> bool:
    if p1.bank_id != p2.bank_id:
        return False

    if not _merchants_match(p1.merchant_name, p2.merchant_name):
        return False

    if not _benefits_match(p1.benefit_type, p2.benefit_type):
        return False

    if not _discounts_match(
        float(p1.discount_percent) if p1.discount_percent else None,
        float(p2.discount_percent) if p2.discount_percent else None,
    ):
        return False

    if not _cuotas_match(p1.installment_count, p2.installment_count):
        return False

    return True


def _quality_score(promo: PromotionModel) -> int:
    score = 0

    if promo.merchant_name:
        score += 2
    elif promo.title:
        score += 1

    if promo.discount_percent:
        score += 2
    elif promo.installment_count:
        score += 2

    if promo.valid_from or promo.valid_to or promo.valid_days:
        score += 2

    if promo.category:
        score += 1

    if promo.benefit_type:
        score += 1

    return score


def dedupe_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []

    unique: List[PromotionModel] = []
    seen: List[tuple] = []

    for promo in promos:
        key = (
            promo.bank_id,
            _normalize_for_compare(promo.merchant_name),
            promo.benefit_type.lower() if promo.benefit_type else "",
            float(promo.discount_percent) if promo.discount_percent else None,
            promo.installment_count,
        )

        is_dup = False
        for i, prev_key in enumerate(seen):
            if prev_key == key:
                if _quality_score(promo) > _quality_score(unique[i]):
                    unique[i] = promo
                    seen[i] = key
                is_dup = True
                break

        if not is_dup:
            unique.append(promo)
            seen.append(key)

    return unique