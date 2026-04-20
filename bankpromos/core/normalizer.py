import re
from typing import Optional

from bankpromos.core.models import PromotionModel

MERCHANT_ALIASES = {
    "shell mcal lopez": "Shell",
    "shell madal": "Shell",
    "shell": "Shell",
    "superseis": "Superseis",
    "super 6": "Superseis",
    "supermercado stock": "Stock",
    "stock": "Stock",
    "g秘astro": "Gastronomía",
    "gastr": "Gastronomía",
    "granada": "Granada",
    "cpf": "CPF",
    "bbva": "BBVA",
    "itau": "Itau",
    "santander": "Santander",
    "banco america": "Banco de América",
}

CATEGORY_ALIASES = {
    "gastronomia": "Gastronomía",
    "gastr": "Gastronomía",
    "restaurante": "Gastronomía",
    "restaurant": "Gastronomía",
    "cafe": "Gastronomía",
    "coffee": "Gastronomía",
    "tech": "Tecnología",
    "tecnologia": "Tecnología",
    "tecnol": "Tecnología",
    "electro": "Tecnología",
    "super": "Supermercados",
    "supermerc": "Supermercados",
    "indumentaria": "Indumentaria",
    "ropa": "Indumentaria",
    "moda": "Indumentaria",
    "salud": "Salud",
    "farmacia": "Salud",
    "educacion": "Educación",
    "universidad": "Educación",
    "hogar": "Hogar",
    "muebleria": "Hogar",
    "combustible": "Combustible",
    "estacion": "Combustible",
    "viajes": "Viajes",
    "vacaciones": "Viajes",
    "automotor": "Automotor",
    "auto": "Automotor",
}

BENEFIT_ALIASES = {
    "reintegro": "reintegro",
    "cashback": "reintegro",
    "cash back": "reintegro",
    "descuento": "descuento",
    "discount": "descuento",
    "cuotas": "cuotas",
    "cuota": "cuotas",
    "sin intereses": "sin_interés",
    "sin interes": "sin_interés",
    "0 interes": "sin_interés",
    "0%": "sin_interés",
}


def normalize_merchant_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    normalized = name.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w\s&'-]", "", normalized)
    normalized = normalized.title()

    key = normalized.lower()
    if key in MERCHANT_ALIASES:
        return MERCHANT_ALIASES[key]

    for alias, canonical in MERCHANT_ALIASES.items():
        if alias in key or key in alias:
            return canonical

    if len(normalized) > 30:
        words = normalized.split()
        if len(words) >= 2:
            return words[0]

    return normalized


def normalize_category(category: Optional[str]) -> Optional[str]:
    if not category:
        return None

    normalized = category.strip()
    normalized = normalized.lower()

    if normalized in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[normalized]

    for alias, canonical in CATEGORY_ALIASES.items():
        if alias in normalized or normalized in alias:
            return canonical

    return category.capitalize()


def normalize_benefit_type(benefit_type: Optional[str], title: str, detail: str) -> Optional[str]:
    if benefit_type:
        normalized = benefit_type.lower().strip()
        if normalized in BENEFIT_ALIASES:
            return BENEFIT_ALIASES[normalized]
        return benefit_type

    text = f"{title} {detail}".lower()

    for alias, canonical in BENEFIT_ALIASES.items():
        if alias in text:
            return canonical

    if re.search(r"\d+\s*%", text):
        if "reintegro" in text:
            return "reintegro"
        return "descuento"

    if re.search(r"\d+\s*cuotas?", text):
        return "cuotas"

    if re.search(r"sin\s*interes|0%", text):
        return "sin_interés"

    return None


def normalize_promotion(promo: PromotionModel) -> PromotionModel:
    merchant = normalize_merchant_name(promo.merchant_name)
    if not merchant and promo.title:
        merchant = normalize_merchant_name(promo.title)

    category = normalize_category(promo.category)
    if not category:
        category = promo.category

    benefit_type = normalize_benefit_type(
        promo.benefit_type, promo.title or "", promo.raw_text or ""
    )

    valid_days = sorted(list(set(promo.valid_days))) if promo.valid_days else []

    return PromotionModel(
        bank_id=promo.bank_id,
        title=promo.title.strip() if promo.title else promo.title,
        merchant_name=merchant,
        category=category,
        benefit_type=benefit_type,
        discount_percent=promo.discount_percent,
        installment_count=promo.installment_count,
        valid_days=valid_days,
        valid_from=promo.valid_from,
        valid_to=promo.valid_to,
        source_url=promo.source_url,
        raw_text=promo.raw_text,
        raw_data=promo.raw_data,
        scraped_at=promo.scraped_at,
    )