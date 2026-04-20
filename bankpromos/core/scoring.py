from bankpromos.core.models import PromotionModel


def calculate_quality_score(promo: PromotionModel) -> float:
    score = 0.0

    if promo.merchant_name:
        score += 2.0
    elif promo.title:
        score += 1.0

    if promo.discount_percent:
        score += 2.0
    elif promo.installment_count:
        score += 2.0

    if promo.valid_from or promo.valid_to or promo.valid_days:
        score += 2.0

    if promo.category:
        score += 1.0

    if promo.benefit_type:
        score += 1.0

    return score


def get_quality_label(score: float) -> str:
    if score >= 5.0:
        return "HIGH"
    elif score >= 3.0:
        return "MEDIUM"
    else:
        return "LOW"


def score_promotion(promo: PromotionModel) -> PromotionModel:
    score = calculate_quality_score(promo)
    label = get_quality_label(score)

    promo.result_quality_score = score
    promo.result_quality_label = label

    return promo


def score_promotions(promos: list[PromotionModel]) -> list[PromotionModel]:
    return [score_promotion(p) for p in promos]