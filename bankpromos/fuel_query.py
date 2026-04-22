from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

from bankpromos.core.models import FuelPriceModel, PromotionModel
from bankpromos.fuel_prices import (
    find_price,
    get_fuel_prices,
    normalize_emblem,
    normalize_fuel_type,
    PY_FUEL_EMBLEMS,
)


FUEL_KEYWORDS = {"combustible", "nafta", "diesel", "gasolina", "gnc", "estacion", "shell", "copetrol", "petropar", "petrobras", "enex"}


def _is_fuel_promo(promo: PromotionModel) -> bool:
    text = f"{promo.title or ''} {promo.merchant_name or ''} {promo.category or ''} {promo.raw_text or ''}".lower()

    if "combustible" in text or "estacion" in text or "nafta" in text or "diesel" in text or "gnc" in text or "gasolina" in text:
        return True

    if promo.category:
        cat = promo.category.lower()
        if "combustible" in cat:
            return True

    for emblem in PY_FUEL_EMBLEMS:
        if emblem in text:
            return True

    if promo.merchant_name:
        merchant_lower = promo.merchant_name.lower()
        for emb in PY_FUEL_EMBLEMS:
            if emb in merchant_lower:
                return True

    return False


def _extract_emblem_from_text(text: str) -> Optional[str]:
    text_lower = text.lower()

    emblem_map = {
        "shell": ["shell", "shell mcal", "shell madal"],
        "copetrol": ["copetrol"],
        "petropar": ["petropar"],
        "petrobras": ["petrobras"],
        "enex": ["enex"],
    }

    for emblem, aliases in emblem_map.items():
        for alias in aliases:
            if alias in text_lower:
                return emblem

    for emblem in PY_FUEL_EMBLEMS:
        if emblem in text_lower:
            return emblem

    return None


def _calculate_final_price(base_price: Decimal, discount_percent: Optional[Decimal]) -> Decimal:
    if not discount_percent or discount_percent == 0:
        return base_price

    return base_price * (Decimal("1") - discount_percent / Decimal("100"))


def _calculate_savings(base_price: Decimal, final_price: Decimal) -> Decimal:
    return base_price - final_price


def find_best_fuel_promotions(
    promos: List[PromotionModel],
    fuel_prices: List[FuelPriceModel],
    fuel_type: str,
    emblem: Optional[str] = None,
) -> List[Dict[str, Any]]:
    fuel_promos = [p for p in promos if _is_fuel_promo(p)]

    if not fuel_promos:
        return []

    if not fuel_prices:
        fuel_prices = get_fuel_prices()

    if not fuel_prices:
        return []

    filtered_emblem = normalize_emblem(emblem) if emblem else None
    filtered_fuel_type = normalize_fuel_type(fuel_type)

    if not filtered_fuel_type:
        filtered_fuel_type = "nafta_95"

    matches: List[Dict[str, Any]] = []

    fuel_price = find_price(fuel_prices, filtered_fuel_type, filtered_emblem) if filtered_emblem else None

    if not fuel_price and filtered_emblem:
        for fp in fuel_prices:
            if fp.fuel_type == filtered_fuel_type:
                fuel_price = fp
                break

    if not fuel_price:
        fp = find_price(fuel_prices, filtered_fuel_type, "shell")
        if fp:
            fuel_price = fp
        else:
            for fp in fuel_prices:
                if fp.fuel_type == filtered_fuel_type:
                    fuel_price = fp
                    break

    if not fuel_price:
        return []

    base_price = fuel_price.price

    for promo in fuel_promos:
        promo_text = f"{promo.title or ''} {promo.merchant_name or ''} {promo.raw_text or ''}".lower()

        promo_emblem = _extract_emblem_from_text(promo_text)

        if filtered_emblem and promo_emblem and promo_emblem != filtered_emblem:
            continue

        if filtered_emblem and not promo_emblem:
            promo_base_fuel = find_price(fuel_prices, filtered_fuel_type, filtered_emblem)
            if promo_base_fuel:
                promo_base = promo_base_fuel.price
            else:
                promo_base = base_price
        elif promo_emblem:
            promo_base_fuel = find_price(fuel_prices, filtered_fuel_type, promo_emblem)
            promo_base = promo_base_fuel.price if promo_base_fuel else base_price
        else:
            promo_base = base_price

        discount = promo.discount_percent
        if not discount:
            if promo.benefit_type == "reintegro":
                discount = promo.discount_percent
            elif promo.benefit_type == "descuento":
                discount = promo.discount_percent
            else:
                discount = promo.discount_percent

        final_price = _calculate_final_price(promo_base, discount)
        savings = _calculate_savings(promo_base, final_price)

        quality = promo.result_quality_score or 0.0

        matches.append({
            "bank_id": promo.bank_id,
            "emblem": promo_emblem or fuel_price.emblem,
            "fuel_type": filtered_fuel_type,
            "base_price": promo_base,
            "discount_percent": discount,
            "estimated_final_price": final_price,
            "savings": savings,
            "valid_days": promo.valid_days,
            "source_url": promo.source_url,
            "quality_score": quality,
            "promo_title": promo.title,
            "merchant_name": promo.merchant_name,
        })

    matches.sort(
        key=lambda x: (
            x["estimated_final_price"],
            -(x["discount_percent"] or Decimal("0")),
            -x["quality_score"],
        )
    )

    return matches[:10]


def parse_fuel_intent(query: str) -> Dict[str, Any]:
    query_lower = query.lower()

    is_fuel = False

    for kw in FUEL_KEYWORDS:
        if kw in query_lower:
            is_fuel = True
            break

    fuel_type = normalize_fuel_type(query)
    emblem = normalize_emblem(query)

    return {
        "is_fuel_query": is_fuel,
        "fuel_type": fuel_type,
        "emblem": emblem,
    }


def get_fuel_results(
    promos: List[PromotionModel],
    fuel_type: str,
    emblem: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    fuel_prices = get_fuel_prices()

    matches = find_best_fuel_promotions(promos, fuel_prices, fuel_type, emblem)

    return matches[:limit]


def format_fuel_result(result: Dict[str, Any], rank: int) -> str:
    bank = result["bank_id"].replace("py_", "").upper()
    emblem = result["emblem"].upper()
    fuel_t = result["fuel_type"].replace("nafta_", "").replace("_", " ")

    base = float(result["base_price"])
    disc = result["discount_percent"]
    final = float(result["estimated_final_price"])

    disc_str = f"{int(disc)}%" if disc else "0%"
    final_str = f"{final:,.0f}"

    days = ", ".join(result["valid_days"]) if result["valid_days"] else "todos"

    return f"{rank:2}. [{bank}] {emblem:10} | {fuel_t:5} | {base:,.0f} → {final_str} ({disc_str}) | {days}"