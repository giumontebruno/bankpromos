import re
from datetime import date
from typing import Optional, Tuple
from decimal import Decimal


def parse_spanish_date(text: str) -> Tuple[Optional[date], Optional[date]]:
    valid_from = None
    valid_to = None
    text_lower = text.lower()
    month_map = {
        "ene": 1, "enero": 1,
        "feb": 2, "febrero": 2,
        "mar": 3, "marzo": 3,
        "abr": 4, "abril": 4,
        "may": 5, "mayo": 5,
        "jun": 6, "junio": 6,
        "jul": 7, "julio": 7,
        "ago": 8, "agosto": 8,
        "sep": 9, "septiembre": 9,
        "oct": 10, "octubre": 10,
        "nov": 11, "noviembre": 11,
        "dic": 12, "diciembre": 12,
    }
    year_match = re.search(r"20(\d{2})", text)
    year = 2026
    if year_match:
        try:
            y = int(year_match.group(1))
            year = 2000 + y if y < 100 else y
        except:
            pass
    patterns = [
        r"(?:desde|desdel)\s*(?:el\s*)?(\d{1,2})\s*de\s*(\w+)\s*(?:hasta|al)\s*(?:el\s*)?(\d{1,2})\s*de\s*(\w+)",
        r"(\d{1,2})\s*de\s*(\w+)\s*(?:hasta|al)\s*(\d{1,2})\s*de\s*(\w+)",
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:al|-)\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
        r"válido\s*(?:del\s*)?(\d{1,2})\s*(\w+)\s*(?:al\s*)?(\d{1,2})\s*(\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            try:
                g = match.groups()
                if len(g) == 4:
                    d1_str, m1_name, d2_str, m2_name = g
                    if d1_str and m1_name in month_map and d2_str and m2_name in month_map:
                        d1 = int(d1_str)
                        d2 = int(d2_str)
                        m1 = month_map.get(m1_name, 1)
                        m2 = month_map.get(m2_name, 12)
                        if 1 <= d1 <= 31 and 1 <= d2 <= 31:
                            valid_from = date(year, m1, d1)
                            valid_to = date(year, m2, d2)
                            break
                elif len(g) == 6:
                    d1_str, m1_str, y1_str, d2_str, m2_str, y2_str = g
                    if all([d1_str, m1_str, d2_str, m2_str]):
                        d1, m1, d2, m2 = int(d1_str), int(m1_str), int(d2_str), int(m2_str)
                        if 1 <= d1 <= 31 and 1 <= m1 <= 12 and 1 <= d2 <= 31 and 1 <= m2 <= 12:
                            y = int(y2_str) if len(y2_str) == 4 else (2000 + int(y2_str))
                            valid_from = date(y, m1, d1)
                            valid_to = date(y, m2, d2)
                            break
            except Exception:
                pass
    return valid_from, valid_to


def parse_cap_amount(text: str) -> Optional[Decimal]:
    """Parse cap/tope amounts like 'Gs. 150.000' or 'Tope de compra Gs. 1.000.000'"""
    text_lower = text.lower()
    
    context_kw = ["tope", "compra", "reintegro", "máximo", "maximo", "gs", "límite", "monto"]
    if not any(kw in text_lower for kw in context_kw):
        return None
    
    patterns = [
        r"gs\.?\s*([\d.]+)",
        r"tope[:\s]*([\d.]+)",
        r"reintegro\s*(máximo|maximo)?[:\s]*([\d.]+)",
        r"compra\s*(máximo|maximo)?[:\s]*([\d.]+)",
        r"([\d.]{3,})\s*(?:gs|guaraníes|guaranies)",
        r"([\d.]{2,})\s*(?:millones|millón)\s*(?:de\s+)?(?:gs)?",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            amount_str = match.group(1).replace(".", "").replace(",", "")
            if amount_str.isdigit() and len(amount_str) >= 3:
                try:
                    val = int(amount_str)
                    if val >= 5000:
                        return Decimal(val)
                    elif val >= 1000 and any(kw in text_lower for kw in context_kw):
                        return Decimal(val)
                except:
                    pass
    
    millions_match = re.search(r"(\d+(?:,\d+)?)\s*(?:millones|millón)\s*(?:de\s+)?(?:gs)?", text_lower)
    if millions_match:
        try:
            millions_str = millions_match.group(1).replace(",", ".")
            millions = float(millions_str)
            if millions >= 0.5:
                return Decimal(int(millions * 1000000))
        except:
            pass
    
    return None
    
    patterns = [
        r"Gs\.?\s*([\d.]+)",
        r"tope[:\s]*([\d.]+)",
        r"reintegro\s*(máximo|maximo)?[:\s]*([\d.]+)",
        r"compra\s*(máximo|maximo)?[:\s]*([\d.]+)",
        r"([\d.]{3,})\s*(?:Gs|gs|guaraníes|guaranies)",
        r"([\d.]{2,})\s*(?:millones|millón)\s*(?:de\s+)?(?:Gs|gs)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            amount_str = match.group(1).replace(".", "").replace(",", "")
            if amount_str.isdigit() and len(amount_str) >= 3:
                try:
                    val = int(amount_str)
                    if val >= 5000:
                        return Decimal(val)
                    elif val >= 1000 and any(kw in text_lower for kw in context_kw):
                        return Decimal(val)
                except:
                    pass
    
    millions_match = re.search(r"(\d+(?:,\d+)?)\s*(?:millones|millón)\s*(?:de\s+)?(?:Gs|gs)?", text_lower)
    if millions_match:
        try:
            millions_str = millions_match.group(1).replace(",", ".")
            millions = float(millions_str)
            if millions >= 0.5:
                return Decimal(int(millions * 1000000))
        except:
            pass
    
    return None