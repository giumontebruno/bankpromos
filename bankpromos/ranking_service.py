from typing import List, Dict, Any, Optional
from datetime import datetime


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
        
        for fake in FAKE_MERCHANT_PATTERNS:
            if fake in merchant_lower:
                break
        else:
            for kw in FAKE_MERCHANT_PATTERNS:
                if kw in merchant_lower:
                    break
            else:
                if merchant_lower in BANK_NAMES:
                    pass
                elif _is_generic_promo(title, merchant):
                    pass
                else:
                    for legal_kw in LEGAL_BANKING_KEYWORDS:
                        if legal_kw in title_lower or legal_kw in raw_lower:
                            break
                    else:
                        if not merchant and not title:
                            pass
                        elif category == "General" and not merchant and not p.get("discount_percent") and not p.get("installment_count"):
                            pass
                        elif not p.get("discount_percent") and not p.get("installment_count") and not p.get("benefit_type"):
                            pass
                        else:
                            cap = p.get("cap_amount")
                            p_copy = dict(p)
                            
                            if not p.get("conditions_short"):
                                conditions = p.get("conditions_text") or p.get("raw_text")
                                p_copy["conditions_short"] = format_short_conditions(
                                    conditions,
                                    cap,
                                    p.get("valid_days", []),
                                    p.get("payment_method"),
                                )
                            
                            p_copy["category_priority"] = get_category_priority(category)
                            clean.append(p_copy)
    
    return clean