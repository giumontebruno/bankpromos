from datetime import date
from typing import Any, Dict, List, Optional


CATEGORY_COMERCIOS = {
    "Supermercados": "Supermercados adheridos",
    "Gastronom\u00eda": "Gastronom\u00eda adherida",
    "Combustible": "Estaciones adheridas",
    "Indumentaria": "Tiendas adheridas",
    "Tecnolog\u00eda": "Tech adheridos",
    "Salud": "Farmacias adheridas",
    "Belleza": "Centros adheridos",
    "Viajes": "Viajes adheridos",
    "Hogar": "Hogar adherido",
    "Educaci\u00f3n": "Educaci\u00f3n adherida",
    "Entretenimiento": "Entretenimiento adherido",
    "Servicios": "Servicios adheridos",
}

FUEL_EMBLEMS = {"shell", "copetrol", "petropar", "petrobras", "enex", "fp"}

CATEGORY_LEVEL_MERCHANTS = {
    "reintegro del", "un descuento del", "beneficio del",
    "los meses con", "disfrut", "reintegro adicional del",
    "comercios adheridos", "comercios participantes",
}

BANK_NAMES = {"ueno", "itau", "sudameris", "continental", "bnf", "banco"}


def _is_category_level_promo(merchant: Optional[str], category: Optional[str], title: str = "") -> bool:
    if not merchant or not merchant.strip():
        return True

    m = merchant.lower().strip()
    if m in BANK_NAMES:
        return True

    if m in CATEGORY_LEVEL_MERCHANTS:
        return True

    if m.startswith("reintegro del") or m.startswith("descuento del"):
        return True

    for pattern in CATEGORY_LEVEL_MERCHANTS:
        if pattern in m:
            return True

    title_lower = (title or "").lower()
    if "comercios adheridos" in title_lower or "comercios participantes" in title_lower:
        return True

    if category and category != "General" and not merchant:
        return True

    return False


def _get_promo_type(merchant: Optional[str], category: Optional[str], title: str = "") -> str:
    if _is_category_level_promo(merchant, category, title):
        return "categoria"

    if merchant and merchant.strip():
        if category == "General" or not category:
            return "local"
        return "local"

    return "categoria"


def _get_display_name(merchant: Optional[str], category: Optional[str], title: str = "") -> str:
    if merchant and merchant.strip():
        return merchant.strip()

    if category and category in CATEGORY_COMERCIOS:
        return CATEGORY_COMERCIOS[category]

    if category:
        return category

    return "Comercios adheridos"


def _get_display_title(
    merchant: Optional[str],
    category: Optional[str],
    title: str,
    discount_percent: Optional[float],
    installment_count: Optional[int],
    benefit_type: Optional[str],
) -> str:
    if title and len(title.strip()) > 3:
        clean = title.strip()
        generic_prefixes = (
            "beneficio del ", "reintegro del ", "descuento del ",
            "los meses con ", "un descuento del ",
        )
        for prefix in generic_prefixes:
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix):]
        if len(clean) <= 80:
            return clean

    parts = []
    if discount_percent and discount_percent > 0:
        parts.append(f"{int(discount_percent)}% de reintegro")
    elif installment_count and installment_count > 0:
        parts.append(f"{installment_count} cuotas sin intereses")
    elif benefit_type == "reintegro":
        parts.append("Reintegro")
    elif benefit_type == "descuento":
        parts.append("Descuento")
    elif benefit_type == "cuotas":
        parts.append("Cuotas")

    if parts:
        return parts[0]

    if merchant and merchant.strip():
        return f"Promo en {merchant}"

    if category:
        return f"Promo en {category}"

    return "Promoci\u00f3n"


def _get_display_subtitle(
    valid_days: List[str],
    valid_from: Optional[date],
    valid_to: Optional[date],
    conditions_short: str,
) -> str:
    parts = []

    if valid_days and len(valid_days) > 0:
        day_map = {
            "lunes": "Lun", "martes": "Mar", "miercoles": "Mi\u00e9",
            "mi\u00e9rcoles": "Mi\u00e9", "jueves": "Jue", "viernes": "Vie",
            "sabado": "S\u00e1b", "s\u00e1bado": "S\u00e1b",
            "domingo": "Dom", "domingos": "Dom",
        }
        abbrev = [day_map.get(d.lower(), d[:3].title()) for d in valid_days]
        if len(abbrev) <= 3:
            parts.append(", ".join(abbrev))
        elif len(abbrev) == 7:
            parts.append("Todos los d\u00edas")
        else:
            parts.append(", ".join(abbrev[:3]) + "...")

    if valid_from and valid_to:
        parts.append(f"Vence {valid_to.strftime('%d/%m')}")

    if conditions_short and len(conditions_short) > 3:
        cond = conditions_short[:40]
        if len(conditions_short) > 40:
            cond += "..."
        parts.append(cond)

    return " | ".join(parts)


def _get_highlight(
    discount_percent: Optional[float],
    installment_count: Optional[int],
    benefit_type: Optional[str],
) -> tuple[str, str]:
    if discount_percent and discount_percent > 0:
        pct = int(discount_percent) if discount_percent == int(discount_percent) else discount_percent
        return f"{pct}% OFF", "discount"

    if installment_count and installment_count > 0:
        return f"{installment_count} cuotas", "cuotas"

    if benefit_type == "reintegro":
        return "Cashback", "reintegro"

    if benefit_type == "descuento":
        return "Descuento", "descuento"

    return "", ""


def _format_cap_display(cap_amount: Optional[float]) -> Optional[str]:
    if not cap_amount or cap_amount <= 0:
        return None
    if cap_amount >= 1_000_000:
        return f"Gs. {cap_amount / 1_000_000:.1f}M"
    if cap_amount >= 1_000:
        return f"Gs. {cap_amount:,.0f}"
    return f"Gs. {cap_amount:,.0f}"


def _format_days_display(valid_days: List[str]) -> Optional[str]:
    if not valid_days:
        return None
    day_map = {
        "lunes": "Lun", "martes": "Mar", "miercoles": "Mi\u00e9",
        "mi\u00e9rcoles": "Mi\u00e9", "jueves": "Jue", "viernes": "Vie",
        "sabado": "S\u00e1b", "s\u00e1bado": "S\u00e1b",
        "domingo": "Dom", "domingos": "Dom",
    }
    abbrev = [day_map.get(d.lower(), d[:3].title()) for d in valid_days]
    if len(abbrev) == 7:
        return "Todos los d\u00edas"
    if len(abbrev) == 5 and not ("s\u00e1b" in abbrev or "Dom" in abbrev):
        return "Lun-Vie"
    return ", ".join(abbrev)


def to_ui_promo(promo: Dict[str, Any]) -> Dict[str, Any]:
    bank_id = promo.get("bank_id", "")
    merchant = promo.get("merchant_name") or ""
    category = promo.get("category") or "General"
    title = promo.get("title") or ""
    raw_text = promo.get("raw_text") or ""
    discount_raw = promo.get("discount_percent")
    conditions_text = promo.get("conditions_text") or ""
    conditions_short_raw = promo.get("conditions_short") or ""

    try:
        discount = float(discount_raw) if discount_raw else None
    except (ValueError, TypeError):
        discount = None

    installment = promo.get("installment_count")
    benefit_type = promo.get("benefit_type") or ""

    cap_raw = promo.get("cap_amount")
    try:
        cap_amount = float(cap_raw) if cap_raw else None
    except (ValueError, TypeError):
        cap_amount = None

    valid_days = promo.get("valid_days") or []
    if isinstance(valid_days, str):
        import json
        try:
            valid_days = json.loads(valid_days)
        except Exception:
            valid_days = []

    valid_from_str = promo.get("valid_from")
    valid_to_str = promo.get("valid_to")

    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    if valid_from_str:
        if isinstance(valid_from_str, str):
            try:
                valid_from = date.fromisoformat(valid_from_str[:10])
            except Exception:
                pass
        elif hasattr(valid_from_str, 'year'):
            valid_from = valid_from_str
    if valid_to_str:
        if isinstance(valid_to_str, str):
            try:
                valid_to = date.fromisoformat(valid_to_str[:10])
            except Exception:
                pass
        elif hasattr(valid_to_str, 'year'):
            valid_to = valid_to_str

    is_category_level = _is_category_level_promo(merchant, category, title)
    promo_type = _get_promo_type(merchant, category, title)
    display_name = _get_display_name(merchant, category, title)
    display_title = _get_display_title(merchant, category, title, discount, installment, benefit_type)
    highlight_value, highlight_type = _get_highlight(discount, installment, benefit_type)

    conditions_short = conditions_short_raw
    if not conditions_short and conditions_text:
        cond = conditions_text[:60]
        if len(conditions_text) > 60:
            cond += "..."
        conditions_short = cond
    elif not conditions_short:
        parts = []
        if cap_amount and cap_amount > 0:
            parts.append(f"Tope: {_format_cap_display(cap_amount)}")
        if valid_days:
            parts.append(_format_days_display(valid_days) or "")
        conditions_short = " | ".join(p for p in parts if p)

    display_subtitle = _get_display_subtitle(valid_days, valid_from, valid_to, conditions_short)

    emblem = promo.get("emblem") or ""
    if not emblem:
        raw_lower = f"{raw_text} {title}".lower()
        for e in FUEL_EMBLEMS:
            if e in raw_lower:
                emblem = e.title()
                break

    bank_known_names = {
        "ueno": "Ueno", "py_ueno": "Ueno",
        "itau": "Itau", "py_itau": "Itau",
        "sudameris": "Sudameris", "py_sudameris": "Sudameris",
        "continental": "Continental", "py_continental": "Continental",
        "bnf": "BNF", "py_bnf": "BNF",
    }
    bank_display = bank_known_names.get(bank_id.lower(), bank_id.title()) if bank_id else ""

    result = {
        "bank_id": bank_id,
        "bank_display": bank_display,
        "title": title,
        "merchant_name": merchant or None,
        "category": category,
        "is_category_level": is_category_level,
        "promo_type_display": promo_type,
        "display_name": display_name,
        "display_title": display_title,
        "display_subtitle": display_subtitle,
        "discount_percent": discount,
        "installment_count": installment,
        "cap_amount": cap_amount,
        "cap_display": _format_cap_display(cap_amount),
        "valid_days": valid_days,
        "valid_days_display": _format_days_display(valid_days),
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_to": valid_to.isoformat() if valid_to else None,
        "conditions_text": conditions_text or None,
        "conditions_short": conditions_short or None,
        "benefit_type": benefit_type or None,
        "highlight_value": highlight_value,
        "highlight_type": highlight_type,
        "emblem": emblem or None,
        "source_url": promo.get("source_url") or "",
        "quality_score": promo.get("result_quality_score") or promo.get("quality_score") or 0.0,
        "quality_label": promo.get("result_quality_label") or "UNKNOWN",
    }

    return result


def group_promos_by_category(promos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in promos:
        cat = p.get("category") or "General"
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(p)
    return groups


def group_promos_by_bank(promos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in promos:
        bank = p.get("bank_id") or "unknown"
        if bank not in groups:
            groups[bank] = []
        groups[bank].append(p)
    return groups


def filter_public_promos(
    promos: List[Dict[str, Any]],
    min_discount: float = 0,
    require_benefit: bool = False,
) -> List[Dict[str, Any]]:
    clean = []
    for p in promos:
        merchant = (p.get("merchant_name") or "").lower().strip()
        title = (p.get("title") or "").lower().strip()
        category = p.get("category") or "General"

        if merchant in BANK_NAMES:
            continue

        if merchant.startswith("reintegro del") or merchant.startswith("descuento del"):
            continue

        if "comercios adheridos" in merchant or "comercios participantes" in merchant:
            pass

        if require_benefit:
            if not p.get("discount_percent") and not p.get("installment_count"):
                continue

        discount_raw = p.get("discount_percent")
        try:
            discount_val = float(discount_raw) if discount_raw else 0.0
        except (ValueError, TypeError):
            discount_val = 0.0

        if discount_val < min_discount and not p.get("installment_count"):
            continue

        if category == "General" and not merchant and not p.get("discount_percent"):
            continue

        clean.append(p)

    return clean