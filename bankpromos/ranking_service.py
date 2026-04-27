from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import re
except ImportError:
    raise RuntimeError("Missing required module: re")


CATEGORY_PRIORITY = {
    "Combustible": 1,
    "Supermercados": 2,
    "Gastronomía": 3,
    "Tecnología": 4,
    "Indumentaria": 5,
    "Salud": 6,
    "Viajes": 7,
    "Hogar": 8,
    "Belleza": 9,
    "Entretenimiento": 10,
    "Educación": 11,
    "Servicios": 12,
    "General": 50,
}


def get_category_priority(category: Optional[str]) -> int:
    return CATEGORY_PRIORITY.get(category or "", 99)


def diversify_promos(
    promos: List[Dict[str, Any]],
    max_per_category: int = 3,
    min_categories: int = 3,
) -> List[Dict[str, Any]]:
    if not promos:
        return []
    
    priority_cats = ["Supermercados", "Combustible", "Gastronomía"]
    
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for p in promos:
        cat = p.get("category") or "Otro"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)
    
    for cat in by_category:
        by_category[cat].sort(key=lambda x: -(x.get("discount_percent") or 0))
        by_category[cat] = by_category[cat][:max_per_category]
    
    result = []
    for cat in priority_cats:
        if cat in by_category:
            result.extend(by_category.pop(cat))
    
    other_cats = sorted(by_category.keys(), key=lambda c: CATEGORY_PRIORITY.get(c, 99))
    for cat in other_cats:
        result.extend(by_category[cat])
    
    unique_cats = set(p.get("category") for p in result if p.get("category"))
    if len(unique_cats) < min_categories and len(by_category) > 0:
        remaining = []
        for cat in other_cats:
            remaining.extend(by_category[cat])
        remaining.sort(key=lambda x: -(x.get("discount_percent") or 0))
        
        for p in remaining:
            if len(set(pc.get("category") for pc in result)) >= min_categories:
                break
            if p not in result:
                result.append(p)
    
    return result


GENERIC_TITLE_WORDS = {
    "beneficio", "beneficios", "promocion", "promociones", "descuento",
    "oferta", "exclusivo", "exclusivos", "especial", "especiales",
    "obtene", "obten", "hasta", "para vos", "para ti", "vos",
    "comercios", "adheridos", "todos", "generales", "general", "ahorro",
    "conoce", "mas informacion", "consulta", "vigencia", "valido",
}

FAKE_MERCHANT_PATTERNS = [
    "el reintegro del",
    "un reintegro del",
    "reintegro adicional del",
    "un descuento del",
    "los meses con pagos",
    "disfrut",
    "beneficio del",
    "promociones del",
    "descuentos del",
    "reintegro del",
    "descuento del",
    "100 de reintegro", "25 de reintegro", "20 de reintegro", "50 de reintegro",
    "100 de descuento", "25 de descuento", "20 de descuento", "50 de descuento",
    "desde", "vigentes", "al respecto", "reclamo", "cinutoerteasse",
    "el reintegro del", "un reintegro del", "reintegro adicional del",
]

BANK_NAMES = {
    "ueno", "itau", "sudameris", "continental", "bnf", "banco",
    "py_ueno", "py_itau", "py_sudameris", "py_continental", "py_bnf",
}

LEGAL_BANKING_KEYWORDS = [
    "sobregiros", "cheques girados", "contrato único", "impuestos",
    "informes en caso de atraso", "presencia del 100%",
    "los meses con pagos", "plazo de acreditaci", "cheques",
    "sobres", "avales", "garantías", "seguros",
    "accidentes", "personas", "vida", "sueldo",
    "liquidación", "liquidacion", "nómina", "nomina",
    "crédito", "préstamo", "cobranza", "cobro",
    "reclamaciones", "servicio al cliente", "legal",
]

OCR_FIXES = {
    "reinegro": "reintegro",
    "descune": "descuento",
    "copetrol": "copetrol",
    "beneﬁcio": "beneficio",
    "reintegro": "reintegro",
    "descuento": "descuento",
}

TITLE_CLEANUP_PATTERNS = [
    r"\bhacete\s+cliente\b.*",
    r"\btu\s+tarjeta\b.*",
    r"\bbeneficios?\b.*",
    r"\bdescuentos?\b.*",
    r"\bconsulta\s+.*",
    r"\bvalido\s+.*",
    r"\bvigencia\s+.*",
    r"\bexclusivo\s+cliente.*",
    r"\bpara\s+vos.*",
    r"\bpara\s+ti.*",
]


def _clean_title(title: str) -> str:
    if not title:
        return ""
    
    cleaned = title.strip()
    
    for pattern in TITLE_CLEANUP_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()
    
    return cleaned


def _fix_ocr_errors(text: str) -> str:
    if not text:
        return text
    
    for wrong, correct in OCR_FIXES.items():
        if wrong != correct:
            text = re.sub(wrong, correct, text, flags=re.IGNORECASE)
    
    text = re.sub(r"\s+", " ", text)
    return text


def _is_generic_promo(title: str, merchant: Optional[str]) -> bool:
    title_lower = (title or "").lower().strip()
    merchant_lower = (merchant or "").lower().strip()
    
    if title_lower in GENERIC_TITLE_WORDS:
        return True
    for word in GENERIC_TITLE_WORDS:
        if title_lower.startswith(word + " ") or title_lower == word:
            return True
    
    for fake in FAKE_MERCHANT_PATTERNS:
        if fake in merchant_lower:
            return True
    
    if merchant_lower in BANK_NAMES:
        return True
    
    if not merchant or len(merchant) < 2:
        return True
    
    return False


def _calculate_usefulness_score(
    category: Optional[str],
    discount_percent: Optional[float],
    installment_count: Optional[int],
    cap_amount: Optional[float],
    merchant_name: Optional[str],
    title: str,
    valid_days: List[str],
) -> float:
    score = 0.0
    
    score += (10 - get_category_priority(category)) * 10
    
    if discount_percent:
        score += discount_percent * 2
    
    if installment_count:
        score += installment_count
    
    if cap_amount and cap_amount > 0:
        score += 10
    
    if merchant_name and len(merchant_name) >= 2:
        score += 20
    
    if valid_days and len(valid_days) > 0:
        today = datetime.now().weekday()
        day_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
        valid_lower = [d.lower() for d in valid_days]
        if any(day_map.get(d, -1) == today for d in valid_lower):
            score += 30
        if "sabado" in valid_lower or "domingo" in valid_lower:
            score += 5
    
    is_generic = _is_generic_promo(title, merchant_name)
    if is_generic:
        score -= 100
    
    return score


def rank_promos_for_today(promos: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    scored = []
    
    for p in promos:
        title = p.get("title", "")
        merchant = p.get("merchant_name")
        category = p.get("category")
        discount = p.get("discount_percent")
        if discount:
            try:
                discount = float(discount)
            except:
                discount = None
        installments = p.get("installment_count")
        cap = p.get("cap_amount")
        if cap:
            try:
                cap = float(cap)
            except:
                cap = None
        valid_days = p.get("valid_days", [])
        
        usefulness = _calculate_usefulness_score(
            category, discount, installments, cap, merchant, title, valid_days
        )
        
        scored.append((usefulness, p))
    
    scored.sort(key=lambda x: -x[0])
    
    return [p for _, p in scored[:limit]]


def rank_promos_by_category(
    promos: List[Dict[str, Any]],
    category: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    filtered = [p for p in promos if p.get("category") == category or p.get("category", "").lower() == category.lower()]
    return rank_promos_for_today(filtered, limit)


def format_short_conditions(
    conditions: Optional[str],
    cap: Optional[float],
    valid_days: List[str],
    payment_method: Optional[str],
) -> str:
    parts = []
    
    if valid_days and len(valid_days) > 0:
        days_str = ", ".join(valid_days[:3])
        if len(valid_days) > 3:
            days_str += "..."
        parts.append(days_str)
    
    if cap and cap > 0:
        parts.append(f"Tope:Gs.{int(cap):,}")
    
    if payment_method:
        parts.append(payment_method)
    
    if conditions and len(conditions) > 0:
        cond_short = conditions[:50]
        if len(conditions) > 50:
            cond_short += "..."
        parts.append(cond_short)
    
    return " | ".join(parts) if parts else ""


def _has_clear_benefit(promo: Dict[str, Any]) -> bool:
    discount = promo.get("discount_percent")
    installments = promo.get("installment_count")
    benefit_type = promo.get("benefit_type")
    title = (promo.get("title") or "").lower()
    
    if discount and float(discount) > 0:
        return True
    if installments and int(installments) > 0:
        return True
    if benefit_type in ("descuento", "reintegro", "cuotas", "beneficio"):
        return True
    
    benefit_words = ["descuento", "reintegro", "cuotas", "off", "desc", "%"]
    for word in benefit_words:
        if word in title:
            return True
    
    return False


def filter_noise(promos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clean = []
    
    for p in promos:
        title = p.get("title", "") or ""
        merchant = p.get("merchant_name") or ""
        raw_text = p.get("raw_text") or ""
        merchant_lower = merchant.lower().strip()
        title_lower = title.lower().strip()
        raw_lower = raw_text.lower()
        category = p.get("category") or "General"
        
        if not merchant and not title:
            continue
        
        if merchant_lower in BANK_NAMES:
            continue
        
        title = _fix_ocr_errors(title)
        title = _clean_title(title)
        
        if len(title) > 120:
            continue
        
        sentences = title.split(".")
        if len([s for s in sentences if s.strip()]) > 1:
            continue
        
        if not title.strip():
            continue
        
        if not _has_clear_benefit(p):
            continue
        
        for fake in FAKE_MERCHANT_PATTERNS:
            if fake in merchant_lower:
                break
        else:
            for legal_kw in LEGAL_BANKING_KEYWORDS:
                if legal_kw in title_lower or legal_kw in raw_lower:
                    break
            else:
                if category == "General" and not merchant and not p.get("discount_percent") and not p.get("installment_count"):
                    pass
                elif not p.get("discount_percent") and not p.get("installment_count") and not p.get("benefit_type"):
                    pass
                else:
                    p_copy = dict(p)
                    p_copy["title"] = title
                    
                    valid_days = p_copy.get("valid_days") or []
                    if isinstance(valid_days, list):
                        valid_days = list(dict.fromkeys(valid_days))
                        p_copy["valid_days"] = valid_days
                    
                    if not p_copy.get("conditions_short"):
                        conditions = p_copy.get("conditions_text") or p_copy.get("raw_text")
                        p_copy["conditions_short"] = format_short_conditions(
                            conditions,
                            p_copy.get("cap_amount"),
                            p_copy.get("valid_days", []),
                            p_copy.get("payment_method"),
                        )
                    p_copy["category_priority"] = get_category_priority(category)
                    clean.append(p_copy)
    
    return clean