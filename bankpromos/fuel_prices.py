import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set

from bankpromos.core.models import FuelPriceModel

PY_FUEL_EMBLEMS = {"shell", "copetrol", "petropar", "petrobras", "enex", "fp"}

FUEL_TYPE_ALIASES: Dict[str, Set[str]] = {
    "nafta_93": {"93", "nafta 93", "super", "regular", "87", "90"},
    "nafta_95": {"95", "nafta 95", "premium", "95", "96"},
    "nafta_97": {"97", "nafta 97", "super premium", "98"},
    "diesel": {"diesel", "gas oil", "go", "diesel oil", "gnc"},
}


def normalize_fuel_type(text: str) -> Optional[str]:
    if not text:
        return None

    text_clean = text.lower().strip()
    text_clean = text_clean.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    for fuel_type, aliases in FUEL_TYPE_ALIASES.items():
        if text_clean in aliases:
            return fuel_type

        for alias in aliases:
            if alias in text_clean:
                return fuel_type

    if "93" in text_clean or "regular" in text_clean:
        return "nafta_93"
    if "95" in text_clean or "premium" in text_clean:
        return "nafta_95"
    if "97" in text_clean or "98" in text_clean:
        return "nafta_97"
    if "diesel" in text_clean or "go" in text_clean:
        return "diesel"

    return None


def normalize_emblem(text: str) -> Optional[str]:
    if not text:
        return None

    text_clean = text.lower().strip()
    text_clean = text_clean.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    emblem_map = {
        "shell": {"shell", "shell paraguay"},
        "copetrol": {"copetrol", "copetrol py"},
        "petropar": {"petropar", "petropar Paraguay"},
        "petrobras": {"petrobras", "petrobras py"},
        "enex": {"enex", " estaciones", "estacion de servicio enex"},
    }

    for emblem, aliases in emblem_map.items():
        for alias in aliases:
            if alias in text_clean:
                return emblem

    for emblem in PY_FUEL_EMBLEMS:
        if emblem in text_clean:
            return emblem

    return None


def _price_from_text(text: str) -> Optional[Decimal]:
    if not text:
        return None

    text_clean = text.replace(".", "").replace(",", ".")
    text_clean = re.sub(r"[^\d.,]", "", text_clean)

    try:
        price = Decimal(text_clean)
        if 2000 < price < 20000:
            return price
    except Exception:
        pass

    matches = re.findall(r"(\d{4,5})", text_clean)
    if matches:
        try:
            return Decimal(matches[0])
        except Exception:
            pass

    return None


FUEL_PRICES_STATIC: Dict[str, Dict[str, Decimal]] = {
    "shell": {
        "nafta_93": Decimal("8700"),
        "nafta_95": Decimal("9400"),
        "nafta_97": Decimal("10200"),
        "diesel": Decimal("8200"),
    },
    "copetrol": {
        "nafta_93": Decimal("8450"),
        "nafta_95": Decimal("9150"),
        "nafta_97": Decimal("9900"),
        "diesel": Decimal("7950"),
    },
    "petropar": {
        "nafta_93": Decimal("8300"),
        "nafta_95": Decimal("9000"),
        "nafta_97": Decimal("9700"),
        "diesel": Decimal("7800"),
    },
    "petrobras": {
        "nafta_93": Decimal("8550"),
        "nafta_95": Decimal("9250"),
        "nafta_97": Decimal("10000"),
        "diesel": Decimal("8050"),
    },
    "enex": {
        "nafta_93": Decimal("8600"),
        "nafta_95": Decimal("9300"),
        "nafta_97": Decimal("10100"),
        "diesel": Decimal("8100"),
    },
}


def get_fuel_prices(
    use_static: bool = True,
    emblem: Optional[str] = None,
    fuel_type: Optional[str] = None,
) -> List[FuelPriceModel]:
    results: List[FuelPriceModel] = []

    emblems = [emblem] if emblem else list(FUEL_PRICES_STATIC.keys())

    for emb in emblems:
        if emb not in FUEL_PRICES_STATIC:
            continue

        prices_dict = FUEL_PRICES_STATIC[emb]

        fuel_types = [fuel_type] if fuel_type else list(prices_dict.keys())

        for ft in fuel_types:
            if ft not in prices_dict:
                continue

            results.append(
                FuelPriceModel(
                    emblem=emb,
                    fuel_type=ft,
                    price=prices_dict[ft],
                    source_url="static",
                    updated_at=datetime.now(),
                )
            )

    return results


def find_price(
    fuel_prices: List[FuelPriceModel],
    fuel_type: str,
    emblem: str,
) -> Optional[FuelPriceModel]:
    for fp in fuel_prices:
        if fp.fuel_type == fuel_type and fp.emblem == emblem:
            return fp

    for fp in fuel_prices:
        if fp.fuel_type == fuel_type and normalize_emblem(fp.emblem) == normalize_emblem(emblem):
            return fp

    return None