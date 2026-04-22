import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from bankpromos.core.models import PromotionModel
from bankpromos.fuel_prices import normalize_fuel_type as _norm_fuel_type, normalize_emblem as _norm_emblem, PY_FUEL_EMBLEMS

CATEGORY_KEYWORDS: Dict[str, Set[str]] = {
    "combustible": {"combustible", "nafta", "gasolina", "gnc", "estacion", "estacion de servicio", "shell", "copetrol", "petropar", "petrobras", "enex", "pf"},
    "supermercados": {"supermercado", "super", "carrito", "stock", "superseis", "grifo"},
    "gastronomia": {"gastronomia", "restaurante", "restaurant", "bar", "cafe", "coffee", "pizza", "sushi", "delivery", "comida"},
    "tecnologia": {"tecnologia", "tecnologia", "tech", "celular", "smartphone", "electrodomestico", "electro", "computadora", "notebook"},
    "farmacia": {"farmacia", "salud", "clinica", "doctor", "medicamento"},
    "viajes": {"viajes", "vacaciones", "hotel", "aerolinea", "turismo", "turistico"},
    "hogar": {"hogar", "muebleria", "ferreteria", "decoracion", "articulo"},
    "educacion": {"educacion", "universidad", "curso", "estudio", "carrera"},
    "indumentaria": {"ropa", "indumentaria", "moda", "zapateria", "tienda"},
}

BENEFIT_KEYWORDS: Dict[str, Set[str]] = {
    "reintegro": {"reintegro", "cashback", "cash back", "devolucion"},
    "descuento": {"descuento", "discount", "rebaja", "oferta"},
    "cuotas": {"cuota", "cuotas", "sin interes", "sin interes", "0%"},
}

DAY_ALIASES: Dict[str, str] = {
    "hoy": None,
    "lunes": "lunes",
    "martes": "martes",
    "miercoles": "miércoles",
    "jueves": "jueves",
    "viernes": "viernes",
    "sabado": "sábado",
    "sabados": "sábado",
    "domingo": "domingo",
    "domingos": "domingo",
    "weekend": "sábado",
}


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    text = text.replace("ñ", "n")
    return text


def _is_fuel_query_detected(query: str) -> bool:
    query_lower = query.lower()
    fuel_terms = {"combustible", "nafta", "diesel", "gasolina", "gnc", "estacion", "shell", "copetrol", "petropar", "petrobras", "enex"}
    for term in fuel_terms:
        if term in query_lower:
            return True
    return False


def parse_fuel_intent(query: str) -> Dict[str, Any]:
    return {
        "is_fuel_query": _is_fuel_query_detected(query),
        "fuel_type": _norm_fuel_type(query),
        "emblem": _norm_emblem(query),
    }


def _detect_category(query: str) -> Optional[str]:
    if _is_fuel_query_detected(query):
        return "combustible"

    query_norm = _normalize_text(query)

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in query_norm:
                return category

    return None


def _detect_benefit_type(query: str) -> Optional[str]:
    query_norm = _normalize_text(query)

    for benefit, keywords in BENEFIT_KEYWORDS.items():
        for kw in keywords:
            if kw in query_norm:
                return benefit

    return None


def _detect_day(query: str) -> Optional[str]:
    query_norm = _normalize_text(query)

    for alias, day in DAY_ALIASES.items():
        if alias in query_norm:
            if alias == "hoy":
                weekday = datetime.now().weekday()
                day_map = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}
                return day_map.get(weekday)
            return day

    return None


def _extract_keywords(query: str) -> List[str]:
    query_norm = _normalize_text(query)

    all_stopwords = set()
    for kw_set in CATEGORY_KEYWORDS.values():
        all_stopwords.update(kw_set)
    for kw_set in BENEFIT_KEYWORDS.values():
        all_stopwords.update(kw_set)
    all_stopwords.update(DAY_ALIASES.keys())
    all_stopwords.update({"y", "el", "la", "los", "las", "de", "del", "para", "en", "con", "sin", "hoy", "que", "cual", "mejor", "donde", "como", "que"})

    words = re.findall(r"\w+", query_norm)
    keywords = [w for w in words if w not in all_stopwords and len(w) > 2]

    return keywords


def _category_match(promo: PromotionModel, category: Optional[str]) -> bool:
    if not category:
        return True

    promo_text = _normalize_text(f"{promo.title or ''} {promo.merchant_name or ''} {promo.category or ''} {promo.raw_text or ''}")

    category_keywords = CATEGORY_KEYWORDS.get(category, set())
    for kw in category_keywords:
        if kw in promo_text:
            return True

    if promo.category:
        promo_cat_norm = _normalize_text(promo.category)
        if category in promo_cat_norm or promo_cat_norm in category:
            return True

    if category == "combustible":
        for emblem in PY_FUEL_EMBLEMS:
            if emblem in promo_text:
                return True

    return False


def _benefit_match(promo: PromotionModel, benefit_type: Optional[str]) -> bool:
    if not benefit_type:
        return True

    promo_benefit = (promo.benefit_type or "").lower()
    if benefit_type in promo_benefit:
        return True

    if benefit_type == "reintegro" and ("reintegro" in promo_benefit or "cashback" in promo_benefit):
        return True
    if benefit_type == "descuento" and "descuento" in promo_benefit:
        return True
    if benefit_type == "cuotas" and promo.installment_count:
        return True

    return False


def _day_match(promo: PromotionModel, day: Optional[str]) -> bool:
    if not day:
        return True

    if promo.valid_days:
        return day in [d.lower() for d in promo.valid_days]

    return True


def _keyword_match(promo: PromotionModel, keywords: List[str]) -> bool:
    if not keywords:
        return True

    promo_text = _normalize_text(f"{promo.title or ''} {promo.merchant_name or ''} {promo.raw_text or ''}")

    for kw in keywords:
        if kw in promo_text:
            return True

    return False


def _calculate_relevance_score(promo: PromotionModel) -> float:
    score = 0.0

    if promo.discount_percent:
        score += float(promo.discount_percent)

    if promo.installment_count:
        score += promo.installment_count * 2

    score += promo.result_quality_score or 0.0

    return score


def _sort_key(promo: PromotionModel):
    score = _calculate_relevance_score(promo)

    discount = float(promo.discount_percent) if promo.discount_percent else 0
    cuotas = promo.installment_count or 0
    quality = promo.result_quality_score or 0.0

    return (-discount, -cuotas, -quality, promo.title or "")


def query_promotions(
    promos: List[PromotionModel],
    query: str
) -> List[PromotionModel]:
    if not promos:
        return []

    if not query or not query.strip():
        sorted_promos = sorted(promos, key=_sort_key)
        return sorted_promos[:10]

    category = _detect_category(query)
    benefit_type = _detect_benefit_type(query)
    day = _detect_day(query)
    keywords = _extract_keywords(query)

    filtered: List[PromotionModel] = []

    for promo in promos:
        if not _category_match(promo, category):
            continue
        if not _benefit_match(promo, benefit_type):
            continue
        if not _day_match(promo, day):
            continue
        if not _keyword_match(promo, keywords):
            continue

        filtered.append(promo)

    if not filtered:
        filtered = [p for p in promos if _keyword_match(p, keywords)]

    sorted_promos = sorted(filtered, key=_sort_key)

    return sorted_promos[:10]


def format_promotion(promo: PromotionModel) -> str:
    bank_display = promo.bank_id.replace("py_", "").upper()

    merchant = promo.merchant_name or promo.title or "N/A"

    if promo.discount_percent:
        benefit = f"{int(promo.discount_percent)}% {'reintegro' if promo.benefit_type == 'reintegro' else 'descuento'}"
    elif promo.installment_count:
        benefit = f"{promo.installment_count} cuotas"
    else:
        benefit = promo.benefit_type or "N/A"

    days = ", ".join(promo.valid_days) if promo.valid_days else " todos los días"

    category = promo.category or "General"

    return f"[{bank_display}] {merchant} | {benefit} | {days} | {category}"


def query_and_format(
    promos: List[PromotionModel],
    query: str
) -> List[str]:
    results = query_promotions(promos, query)
    return [format_promotion(p) for p in results]