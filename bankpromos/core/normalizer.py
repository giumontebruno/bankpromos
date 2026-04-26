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
    "gastronomo": "Gastronomía",
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

INVALID_MERCHANT_PATTERNS = {
    "pure_numbers": [r"^\d+$", r"^\d+\s*$"],
    "generic_words": {
        "obtene", "obtené", "hasta", "promociones", "beneficios", "vigencia",
        "valido", "válido", "consumo", "exclusivo", "exclusivos", "exclusiva",
        "aplica", "aplican", "condiciones", "consulta", "ver mas", "ver más",
        "conoce", "descubre", "nuevos", "nueva", "nuevas", "disfruta",
        "especial", "limitado", "stock", "cat", "catálogo", "catalogo",
        "todo", "todos", "todas", "dias", "días", "lunes", "martes",
        "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado",
        "domingo", "domingos", "general", "beneficios para vos",
        "beneficios para ti", "para vos", "para ti",
        "impuestos", "proceda", "contrato único", "el reintegro del",
        "un descuento del", "reintegro del", "descuento del", "reintegro adicional del",
        "beneficio del", "40 de reintegro", "reintegro del 100",
        "presencia del", "plazo de acreditaci",
    },
    "percentage_fragments": {
        "%", "%", "%", "%", "%", "%", "%", "%", "%", "%", "%",
    },
    "bank_names": {
        "ueno", "sudameris", "itau", "continental", "bnf", "banco",
        "banco de la nacion", "banco nacional", "bancosudameris",
    },
}

FUEL_EMBLEMS = {"shell", "copetrol", "petropar", "petrobras", "enex", "fp"}


def _is_valid_merchant_candidate(text: Optional[str]) -> bool:
    if not text:
        return False

    cleaned = text.strip()
    if not cleaned:
        return False

    cleaned_lower = cleaned.lower()

    if len(cleaned) <= 2:
        return False

    if re.match(r"^\d+$", cleaned):
        return False

    for pattern in INVALID_MERCHANT_PATTERNS["pure_numbers"]:
        if re.match(pattern, cleaned):
            return False

    for word in INVALID_MERCHANT_PATTERNS["generic_words"]:
        if cleaned_lower == word or cleaned_lower == f"% {word}%" or cleaned_lower.startswith(f"{word} "):
            return True

    if len(cleaned) >= 2 and cleaned.isdigit():
        return False

    if len(cleaned) <= 3 and cleaned.isalpha():
        return False

    percent_match = re.match(r"^\d+\s*%?\s*$", cleaned)
    if percent_match:
        return False

    if cleaned_lower in {"%"}:
        return False

    return True


def _is_valid_merchant_name(text: Optional[str]) -> bool:
    if not text:
        return False
    
    if not _is_valid_merchant_candidate(text):
        return False
    
    cleaned_lower = text.lower().strip()
    
    valid_generic_words = {"stock"}
    for word in INVALID_MERCHANT_PATTERNS["generic_words"]:
        if cleaned_lower == word and cleaned_lower not in valid_generic_words:
            return False
    
    if cleaned_lower in INVALID_MERCHANT_PATTERNS["bank_names"]:
        return False
    
    if re.match(r"^\d+\s*%?$", text):
        return False
    
    if text.strip().isdigit():
        return False
    
    if any(bank in cleaned_lower for bank in INVALID_MERCHANT_PATTERNS["bank_names"]):
        return False
    
    if cleaned_lower.startswith("reintegro") or cleaned_lower.startswith("descuento"):
        return False
    
    return True


def _contains_fuel_signal(text: str) -> bool:
    text_lower = text.lower()
    fuel_signals = {
        "combustible", "estacion de servicio", "estacion", "shell", "copetrol",
        "petropar", "petrobras", "enex", "nafta", "diesel", "gnc", "gasolina",
        "reintegro combustible", "descuento combustible", "estacion shell",
    }
    for signal in fuel_signals:
        if signal in text_lower:
            return True
    return False


def normalize_merchant_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    if not _is_valid_merchant_candidate(name):
        return None

    normalized = name.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w\s&'-]", "", normalized)
    normalized = normalized.title()

    if not _is_valid_merchant_name(normalized):
        return None

    key = normalized.lower()
    if key in MERCHANT_ALIASES:
        return MERCHANT_ALIASES[key]

    for alias, canonical in MERCHANT_ALIASES.items():
        if alias in key or key in alias:
            return canonical

    if len(normalized) > 30:
        words = normalized.split()
        if len(words) >= 2:
            candidate = words[0]
            if _is_valid_merchant_name(candidate):
                return candidate
            return None

    return normalized


def normalize_category(category: Optional[str], raw_text: str = "") -> Optional[str]:
    if not category:
        if raw_text and _contains_fuel_signal(raw_text):
            return "Combustible"
        return None

    normalized = category.strip()
    normalized = normalized.lower()

    if normalized in CATEGORY_ALIASES:
        result = CATEGORY_ALIASES[normalized]
        if result == "Combustible":
            return "Combustible"
        return result

    for alias, canonical in CATEGORY_ALIASES.items():
        if alias in normalized or normalized in alias:
            return canonical

    if "combustible" in normalized or "estacion" in normalized or "shell" in normalized:
        return "Combustible"

    if raw_text and _contains_fuel_signal(raw_text):
        return "Combustible"

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


def _infer_category_from_text(title: str, detail: str = "") -> Optional[str]:
    txt = f"{title} {detail}".lower()

    rules = [
        (["combustible", "estacion", "shell", "petro", "copetrol", "petropar", "petrobras", "enex", "nafta", "diesel"], "Combustible"),
        (["supermercado", "carrito", "stock", "superseis"], "Supermercados"),
        (["gastr", "restaur", "bar", "coffee", "pizza", "sushi", "comida", "delivery"], "Gastronomía"),
        (["ropa", "indumentaria", "moda", "zapateria"], "Indumentaria"),
        (["tecnología", "celular", "tech", "smart", "electro"], "Tecnología"),
        (["universidad", "curso", "educacion", "estudio"], "Educación"),
        (["farmacia", "salud", "clinica"], "Salud"),
        (["hogar", "muebleria", "ferreteria"], "Hogar"),
        (["viaje", "vacaciones", "hotel"], "Viajes"),
    ]

    for keywords, category in rules:
        if any(kw in txt for kw in keywords):
            return category

    return None


def _is_actionable_promotion(promo: PromotionModel) -> bool:
    merchant = (promo.merchant_name or "").strip().lower()
    raw = (promo.raw_text or "").lower()
    title = (promo.title or "").strip().lower()

    if merchant and _is_valid_merchant_name(merchant):
        return True

    if _contains_fuel_signal(raw):
        return True

    if promo.discount_percent and float(promo.discount_percent) >= 10:
        return True

    if promo.installment_count and promo.installment_count >= 3:
        return True

    return False


def _is_weak_promotion(promo: PromotionModel) -> bool:
    return not _is_actionable_promotion(promo)


from datetime import date, datetime
from typing import Optional, List

from bankpromos.core.models import PromotionModel

DAY_MAP = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
    "domingos": 6,
}

CATEGORIES = [
    "Combustible",
    "Supermercados",
    "Gastronomía",
    "Indumentaria",
    "Tecnología",
    "Farmacia",
    "Salud",
    "Hogar",
    "Viajes",
    "Educación",
    "Belleza",
    "Servicios",
    "Entretenimiento",
    "General",
]


def get_today_day_name() -> str:
    days = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    return days[datetime.now().weekday()]


def _is_active_today(promo: PromotionModel) -> bool:
    today = datetime.now().date()
    
    if promo.valid_from and promo.valid_from > today:
        return False
    if promo.valid_to and promo.valid_to < today:
        return False
    
    if promo.valid_days:
        today_idx = datetime.now().weekday()
        for day in promo.valid_days:
            if day.lower() in DAY_MAP and DAY_MAP[day.lower()] == today_idx:
                return True
        return False
    
    return True


def get_best_promotions_today(
    promos: List[PromotionModel],
    category: Optional[str] = None,
    limit: int = 20,
) -> List[PromotionModel]:
    filtered = [p for p in promos if _is_active_today(p)]
    
    if category:
        cat_lower = category.lower()
        filtered = [
            p for p in filtered
            if p.category and cat_lower in p.category.lower()
        ]
    
    filtered = [
        p for p in filtered
        if p.merchant_name and _is_valid_merchant_name(p.merchant_name)
        or p.category in CATEGORIES[:6]
    ]
    
    def score(p: PromotionModel) -> float:
        s = p.result_quality_score or 0.0
        
        if p.discount_percent:
            pct = float(p.discount_percent)
            if pct >= 30:
                s += 0.5
            elif pct >= 20:
                s += 0.3
            elif pct >= 10:
                s += 0.2
        
        if p.installment_count and p.installment_count >= 6:
            s += 0.3
        
        if p.merchant_name:
            s += 0.2
        
        return s
    
    return sorted(filtered, key=score, reverse=True)[:limit]


def normalize_promotion(promo: PromotionModel) -> Optional[PromotionModel]:
    merchant = normalize_merchant_name(promo.merchant_name)

    if not merchant and promo.title:
        title_merchant = normalize_merchant_name(promo.title)
        if title_merchant and _is_valid_merchant_name(title_merchant):
            merchant = title_merchant

    category = normalize_category(promo.category, promo.raw_text or "")
    if not category:
        inferred = _infer_category_from_text(promo.title or "", promo.raw_text or "")
        if inferred:
            category = inferred
        else:
            category = promo.category

    benefit_type = normalize_benefit_type(
        promo.benefit_type, promo.title or "", promo.raw_text or ""
    )

    active_today = _is_active_today(promo)
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
        result_quality_score=promo.result_quality_score,
        result_quality_label=promo.result_quality_label,
        cap_amount=promo.cap_amount,
        payment_method=promo.payment_method,
        conditions_text=promo.conditions_text,
        merchant_group=promo.merchant_group,
        emblem=promo.emblem,
        is_curated=promo.is_curated,
        is_active_today=active_today,
    )