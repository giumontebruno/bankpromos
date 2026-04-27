import json
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import (
    _is_valid_merchant_name,
    _contains_fuel_signal,
    normalize_merchant_name,
    normalize_category,
    normalize_benefit_type,
)

logger = logging.getLogger(__name__)

GENERIC_WORDS = {
    "beneficio", "beneficios", "promocion", "promociones", "descuento",
    "oferta", "exclusivo", "exclusivos", "especial", "especiales",
    "obtene", "obten", "hasta", "para vos", "para ti", "vos",
    "comercios", "adheridos", "todos", "generales", "general", "ahorro",
    "disfruta", "disfrutá", "vigencia", "válido", "valido",
    "consulta", "consultá", "locales", "aplica", "condiciones",
}

BANK_NAMES_BLOCKLIST = {
    "ueno", "ueno black", "ueno bank", "sudameris", "banco sudameris", "itau", "banco itau",
    "continental", "banco continental", "bnf", "banco nacional", "banco de la nacion",
    "py_ueno", "bancosudameris", "bancoudameris",
}

_MONTH_MAP = {
    "ene": 1, "en": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

VALID_EMBLEMS = {"shell", "copetrol", "petropar", "petrobras", "enex", "fp"}

DAY_MAP = {
    "lunes": ["lunes"],
    "martes": ["martes"],
    "miercoles": ["miercoles", "miércoles"],
    "jueves": ["jueves"],
    "viernes": ["viernes"],
    "sabado": ["sabado", "sábado"],
    "domingo": ["domingo", "domingos"],
}


def extract_pdf_text(source: str) -> str:
    if not source:
        return ""
    
    if source.startswith("http"):
        return _extract_pdf_from_url(source)
    
    return _extract_pdf_from_file(source)


def _extract_pdf_from_url(url: str) -> str:
    if not pdfplumber:
        logger.warning("[PDF] pdfplumber not installed")
        return ""
    
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        
        if len(response.content) < 1000:
            logger.warning(f"[PDF] Too small: {len(response.content)} bytes")
            return ""
        
        return _extract_pdf_from_bytes(response.content)
    
    except Exception as e:
        logger.error(f"[PDF] Failed to fetch {url}: {e}")
        return ""


def _extract_pdf_from_file(path: str) -> str:
    if not pdfplumber:
        return ""
    
    try:
        return _extract_pdf_from_bytes(Path(path).read_bytes())
    except Exception as e:
        logger.error(f"[PDF] Failed to read {path}: {e}")
        return ""


def _extract_pdf_from_bytes(data: bytes) -> str:
    if not pdfplumber:
        return ""
    
    try:
        import tempfile
        import warnings
        import io
        import sys
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            path = f.name
        
        text_parts = []
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception:
                        pass
        finally:
            sys.stderr = old_stderr
        
        Path(path).unlink(missing_ok=True)
        return "\n\n".join(text_parts)
    
    except Exception as e:
        logger.error(f"[PDF] Parse error: {e}")
        return ""


def split_pdf_into_blocks(text: str) -> List[str]:
    if not text:
        return []
    
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    if not lines:
        return []
    
    blocks = []
    current_block = []
    block_started = False
    
    promo_signals = [
        r"\d+\s*%",
        r"reintegro",
        r"descuento",
        r"dto\s*\d+",
        r"\d+\s*cuotas?",
    ]
    
    line_break_patterns = [
        r"^={5,}$",
        r"^-{5,}$",
        r"^\*{5,}$",
    ]
    
    for line in lines:
        is_break = any(re.match(p, line) for p in line_break_patterns)
        if is_break:
            if current_block:
                joined = " ".join(current_block)
                if joined:
                    blocks.append(joined)
                current_block = []
                block_started = False
            continue
        
        is_promo = any(re.search(p, line, re.I) for p in promo_signals)
        
        is_header = _is_section_header(line)
        
        if is_header and current_block:
            joined = " ".join(current_block)
            if joined:
                blocks.append(joined)
            current_block = []
            block_started = False
            current_block.append(line)
            block_started = True
        elif is_promo or is_header:
            if current_block and not block_started:
                joined = " ".join(current_block)
                if joined:
                    blocks.append(joined)
                current_block = []
            
            current_block.append(line)
            block_started = True
        elif current_block and block_started:
            if len(line) > 2:
                current_block.append(line)
            if len(" ".join(current_block)) > 150:
                joined = " ".join(current_block)
                if joined:
                    blocks.append(joined)
                current_block = []
                block_started = False
    
    if current_block:
        joined = " ".join(current_block)
        if joined:
            blocks.append(joined)
    
    return [b for b in blocks if len(b) > 20]


def _is_section_header(line: str) -> bool:
    headers = [
        "combustible", "supermercados", "gastronomia", "gastronomía",
        "indumentaria", "tecnologia", "tecnología", "farmacia", "salud",
        "hogar", "viajes", "educacion", "educación", "belleza",
    ]
    lower = line.lower()
    return lower.strip().rstrip(":") in headers or (
        len(line) < 40 and line[0].isupper() and ":" in line
    )


def _has_promo_signal(text: str) -> bool:
    patterns = [
        r"\d+\s*%",
        r"\d+\s*cuotas?",
        r"reintegro",
        r"descuento",
        r" dto ",
    ]
    return any(re.search(p, text, re.I) for p in patterns)


def is_valid_merchant(text: str) -> bool:
    if not text:
        return False
    text_clean = text.strip().rstrip("-").rstrip("/").rstrip(",").rstrip(":").strip()
    text_lower = text_clean.lower()
    if len(text_clean.split()) > 5:
        return False
    blacklist = ["beneficios", "vigencia", "condiciones", "comercio", "promocion", "tarjeta", "banco", "credito", "aplica", "consulta", "valida", "solo"]
    if any(word in text_lower for word in blacklist):
        return False
    return True


def split_merchants(text: str) -> List[str]:
    if not text:
        return []
    cleaned = text.strip().strip("-").strip("/").strip(",").strip()
    parts = re.split(r"\s*[-/,]+\s*", cleaned)
    result = []
    for p in parts:
        p = p.strip().rstrip(":").strip()
        if p and len(p) > 1 and not re.match(r"^[\d\s,\.\-:]+$", p):
            result.append(p)
    return result


def extract_merchant(block: str) -> List[str]:
    first_discount = re.search(r"(\d{1,2})\s*%|hasta\s*(\d+)\s*cuotas?", block, re.I)
    end_pos = first_discount.start() if first_discount else len(block)
    before = block[:end_pos]
    merchants = []
    lines = [ln.strip() for ln in before.splitlines() if ln.strip()]
    for ln in reversed(lines):
        ln = ln.strip().rstrip(" -").rstrip("-").rstrip(":").strip()
        if not ln or len(ln) < 2:
            continue
        if is_valid_merchant(ln):
            merchants.append(ln)
            break
        else:
            splitted = split_merchants(ln)
            if splitted:
                merchants.extend(splitted)
                break
    valid = [m for m in merchants if is_valid_merchant(m)]
    return valid[:4]


def extract_cap(block: str) -> Optional[int]:
    m = re.search(r"(?:tope|m[aá]ximo|top[e]?|hasta)\s*(?:m[aá]ximo|m[aá]x?)?\s*(?:de\s*)?(?:gs?\s*\.?|guaran(?:ties)?)?\.?\s*([\d\.]+)", block, re.I)
    if m:
        num = m.group(1).replace(".", "").replace(",", "")
        if num.isdigit() and len(num) >= 4:
            return int(num)
    m = re.search(r"cap[:\s]*([\d]+)", block, re.I)
    if m:
        num = m.group(1)
        if len(num) >= 4:
            return int(num)
    return None


def extract_discount(block: str) -> Optional[int]:
    patterns = [
        r"\b(\d{1,2})\s*%",
        r"(\d{1,2})%\s*de\s*(reintegro|descuento)",
        r"hasta\s*(\d{1,2})\s*%",
    ]
    for p in patterns:
        m = re.search(p, block, re.I)
        if m:
            return int(m.group(1))
    return None


def extract_installment(block: str) -> Optional[int]:
    m = re.search(r"hasta\s*(\d+)\s*cuotas?", block, re.I)
    if m:
        return int(m.group(1))
    return None


def extract_cap(block: str) -> Optional[int]:
    patterns = [
        r"(?:Tope|m[aá]ximo|top[e]?|hasta)\s*(?:m[aá]ximo|m[aá]x?)?\s*(?:de\s*)?(?:gs?\s*\.?|guaran(?:ties)?)?\.?\s*([\d\.]+)",
        r"Gs\.?\s*([\d\.]+)",
        r"cap[:\s]*([\d]+)",
    ]
    for p in patterns:
        m = re.search(p, block, re.I)
        if m:
            num = m.group(1).replace(".", "").replace(",", "")
            if num.isdigit():
                return int(num)
    return None


def extract_valid_days(block: str) -> List[str]:
    days_found = []
    for ln in block.splitlines()[:10]:
        ln_lower = ln.lower().strip()
        matches = re.findall(r"(?:lunes|martes|miercoles|miercoles|j[v]?|jueves|viernes|s[áa]bado|domingo)", ln_lower)
        days_found.extend([d.title() for d in matches])
    return list(dict.fromkeys(days_found))[:7]


def is_garbage_block(block: str) -> bool:
    if not block or len(block) > 600:
        return True
    block_lower = block.lower()
    garbage_words = ["vigencia", "condiciones", "aplica", "consulta", "beneficios", "nota:", "importante"]
    if any(word in block_lower for word in garbage_words):
        return True
    if extract_discount(block) is None and extract_installment(block) is None:
        return True
    return False


def split_promo_block(text: str, start: int, end: int) -> str:
    ctx_start = max(0, start - 150)
    block = text[ctx_start:end].strip()
    block = re.sub(r"\n{3,}", "\n\n", block)
    return block


def split_by_discount(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    
    promos = []
    seen = set()
    
    discount_patterns = [
        (r"\b(\d{1,2})\s*%", "percent"),
        (r"hasta\s*(\d+)\s*cuotas?", "installment"),
    ]
    
    all_matches = []
    for pattern, ptype in discount_patterns:
        for m in re.finditer(pattern, text, re.I):
            all_matches.append((m.start(), m.end(), ptype, m.group(1)))
    
    all_matches.sort(key=lambda x: x[0])
    
    if not all_matches:
        return []
    
    for i, (start, end, ptype, value) in enumerate(all_matches):
        next_start = all_matches[i + 1][0] if i + 1 < len(all_matches) else len(text)
        
        block = split_promo_block(text, start, next_start)
        
        if is_garbage_block(block):
            continue
        
        merchants = extract_merchant(block)
        if not merchants:
            continue
        
        discount = extract_discount(block) if ptype == "percent" else None
        installment = extract_installment(block) if ptype == "installment" else None
        
        for merchant in merchants:
            if not is_valid_merchant(merchant):
                continue
            
            key = (merchant.strip().lower(), discount, installment)
            if key in seen:
                continue
            seen.add(key)
            
            promo = {
                "merchant": merchant.strip(),
                "discount_percent": discount,
                "installment_count": installment,
                "cap_amount": extract_cap(block),
                "valid_days": extract_valid_days(block),
                "conditions_short": "",
            }
            promos.append(promo)
    
    return promos


def _extract_ueno_promos(text: str, bank_id: str, source_url: str) -> List[PromotionModel]:
    """Special handling for Ueno Black monthly format"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    promos = []
    
    clean_text = " ".join(lines)
    clean_lower = clean_text.lower()
    
    reintegro_matches = list(re.finditer(r"(\d+)\s*%?\s*de reintegro", clean_lower))
    
    for match in reintegro_matches:
        start = match.start()
        end = match.end()
        
        context_start = max(0, start - 100)
        context_end = min(len(clean_text), end + 200)
        context = clean_text[context_start:context_end]
        
        discount = int(match.group(1))
        
        category = "General"
        if "plataformas" in context.lower():
            category = "Tecnología"
        elif "sax" in context.lower():
            category = "Indumentaria"
        elif "souk" in context.lower():
            category = "Gastronomía"
        elif "spirit" in context.lower() or "free" in context.lower():
            category = "Entretenimiento"
        elif "gastronomi" in context.lower():
            category = "Gastronomía"
        elif "bienestar" in context.lower():
            category = "Belleza"
        elif "viaje" in context.lower() or "aeropuerto" in context.lower():
            category = "Viajes"
        elif "della poletti" in context.lower():
            category = "Gastronomía"
        
        installment = None
        cuota_match = re.search(r"(\d+)\s*cuotas?", context.lower())
        if cuota_match:
            installment = int(cuota_match.group(1))
        
        title = f"{discount}% de reintegro"
        if installment:
            title += f" + {installment} cuotas sin intereses"
        
        cap_match = re.search(r"Gs\.?\s*([\d,.]+)", context)
        cap = None
        if cap_match:
            try:
                g1 = cap_match.group(1)
                if g1 is not None:
                    cap_val = g1.replace(".", "").replace(",", "")
                    cap = Decimal(int(cap_val))
            except:
                pass
        
        promo = PromotionModel(
            bank_id=bank_id,
            title=title,
            merchant_name="Ueno",
            category=category,
            benefit_type="reintegro",
            discount_percent=Decimal(discount),
            installment_count=installment,
            valid_days=[],
            source_url=source_url,
            raw_text=context[:500],
            raw_data={"source": "ueno_pdf"},
            cap_amount=cap,
        )
        promos.append(promo)
    
    return promos


def parse_promotions_from_pdf(
    text: str,
    bank_id: str,
    source_url: str = "",
    category_hint: str = None,
    merchant_hint: str = None,
    use_split_parser: bool = True,
) -> List[PromotionModel]:
    text_lower = text.lower()
    
    global_from, global_to = _extract_dates(text)
    
    if merchant_hint == "Ueno" or "black" in text_lower:
        ueno_promos = _extract_ueno_promos(text, bank_id, source_url)
        if ueno_promos:
            for promo in ueno_promos:
                if not promo.valid_from and global_from:
                    promo.valid_from = global_from
                if not promo.valid_to and global_to:
                    promo.valid_to = global_to
                promo.raw_data["extraction_confidence"] = _calculate_confidence(promo)
            return ueno_promos
    
    if use_split_parser:
        return _parse_with_split_parser(text, bank_id, source_url, category_hint, merchant_hint, global_from, global_to)
    
    blocks = split_pdf_into_blocks(text)
    
    promos = []
    for block in blocks:
        promo = _parse_promo_block(block, bank_id, source_url, category_hint, merchant_hint)
        if promo:
            if not promo.valid_from:
                promo.valid_from = global_from
            if not promo.valid_to:
                promo.valid_to = global_to
            promo.raw_data["extraction_confidence"] = _calculate_confidence(promo)
            promos.append(promo)
    
    return promos


def _parse_with_split_parser(
    text: str,
    bank_id: str,
    source_url: str,
    category_hint: str,
    merchant_hint: str,
    global_from,
    global_to,
) -> List[PromotionModel]:
    raw_promos = split_by_discount(text)
    
    promos = []
    for rp in raw_promos:
        merchant = rp.get("merchant", "")
        discount = rp.get("discount_percent")
        installment = rp.get("installment_count")
        cap = rp.get("cap_amount")
        valid_days = rp.get("valid_days", [])
        
        if not merchant and not discount and not installment:
            continue
        
        title = f"{discount}% reintegro" if discount else (f"hasta {installment} cuotas" if installment else "Promo")
        
        category = category_hint or "General"
        if merchant_hint:
            pass
        
        raw_text = f"{merchant} - {title}"[:500]
        
        promo = PromotionModel(
            bank_id=bank_id,
            title=title,
            merchant_name=merchant,
            category=category,
            benefit_type="reintegro" if discount else "cuotas",
            discount_percent=Decimal(discount) if discount else None,
            installment_count=installment,
            valid_days=valid_days,
            valid_from=global_from,
            valid_to=global_to,
            source_url=source_url,
            raw_text=raw_text,
            raw_data={"source": "split_parser"},
            cap_amount=Decimal(cap) if cap else None,
        )
        
        promos.append(promo)
    
    return promos


def _parse_promo_block(
    block: str,
    bank_id: str,
    source_url: str = "",
    category_hint: str = None,
    merchant_hint: str = None,
) -> Optional[PromotionModel]:
    if not block or len(block) < 20:
        return None
    
    if not _has_promo_signal(block):
        return None
    
    if _is_generic_block(block):
        return None
    
    title = _extract_title_from_block(block)
    if not title:
        title = block[:80]
    
    merchant = _extract_merchant_from_block(block, merchant_hint)
    
    discount = _extract_discount_percent(block)
    installment = _extract_installment_count(block)
    benefit_type = _extract_benefit_type(block)
    category = _extract_category_from_block(block, category_hint)
    valid_days = _extract_valid_days(block)
    valid_from, valid_to = _extract_dates(block)
    cap = _extract_cap(block)
    payment_method = _extract_payment_method(block)
    emblem = _extract_emblem(block)
    conditions = _extract_conditions(block)
    
    if not category:
        category = category_hint
    
    if not merchant:
        merchant = merchant_hint
    
    has_discount = discount and int(discount) > 0
    has_installment = installment and installment > 0
    has_cap = cap and cap > 0
    has_days = valid_days and len(valid_days) > 0
    
    if not any([has_discount, has_installment, has_cap, emblem, has_days]):
        return None
    
    if not category and not _extract_category_from_block(block):
        return None
    
    return PromotionModel(
        bank_id=bank_id,
        title=title,
        merchant_name=merchant,
        category=category,
        benefit_type=benefit_type,
        discount_percent=discount,
        installment_count=installment,
        valid_days=valid_days,
        valid_from=valid_from,
        valid_to=valid_to,
        source_url=source_url,
        raw_text=block[:500],
        raw_data={"source": "pdf", "block_index": 0},
        cap_amount=cap,
        payment_method=payment_method,
        conditions_text=conditions,
        emblem=emblem,
    )


def _calculate_confidence(
    promo: PromotionModel,
) -> float:
    score = 0.0
    
    if promo.merchant_name and len(promo.merchant_name) > 1:
        score += 0.25
    
    if promo.discount_percent and int(promo.discount_percent) > 0:
        score += 0.20
    
    if promo.installment_count and promo.installment_count > 0:
        score += 0.15
    
    if promo.category and promo.category not in ["General", None]:
        score += 0.15
    
    if promo.valid_days and len(promo.valid_days) > 0:
        score += 0.10
    
    if promo.cap_amount and promo.cap_amount > 0:
        score += 0.10
    
    if promo.emblem:
        score += 0.10
    
    if promo.benefit_type:
        score += 0.10
    
    if promo.valid_from or promo.valid_to:
        score += 0.05
    
    if promo.conditions_text:
        score += 0.05
    
    return min(score, 1.0)


def _is_generic_block(text: str) -> bool:
    lower = text.lower()
    
    generic_phrases = [
        "beneficios para vos",
        "beneficios para ti",
        "comercios adheridos",
        "locales adheridos",
        "todos los dias",
        "promociones especiales",
        "disfruta los mejores",
        "consulta condiciones",
        "vigencia del",
    ]
    
    for phrase in generic_phrases:
        if phrase in lower:
            return True
    
    words = lower.split()
    generic_count = sum(1 for w in words if w in GENERIC_WORDS)
    if len(words) > 0 and generic_count / len(words) > 0.5:
        return True
    
    if not _contains_fuel_signal(text) and not _has_clear_merchant(text):
        if not re.search(r"\d{1,2}\s*%", text):
            return True
    
    return False


def _has_clear_merchant(text: str) -> bool:
    text_lower = text.lower()
    
    merchant_patterns = [
        r"shell\s+\d+",
        r"copetrol\s+\d+",
        r"petro(par|bras)\s+\d+",
        r"enex\s+\d+",
        r"stock\s+\d+",
        r"superseis\s+\d+",
        r"carrefour\s+\d+",
        r"walmart\s+\d+",
        r"superc\s*\d+",
    ]
    
    return any(re.search(p, text_lower) for p in merchant_patterns)


def _extract_title_from_block(block: str) -> str:
    lines = block.split(".")
    
    for line in lines[:3]:
        line = line.strip()
        if len(line) > 5 and len(line) < 80:
            if _has_promo_signal(line):
                return line
    
    return block[:80]


def _extract_merchant_from_block(block: str, merchant_hint: str = None) -> Optional[str]:
    block_lower = block.lower()
    
    if merchant_hint and merchant_hint not in ("None", "", "ueno", "Ueno", "UENO"):
        if len(merchant_hint) >= 2:
            normalized_hint = normalize_merchant_name(merchant_hint)
            if normalized_hint and normalized_hint.lower() not in BANK_NAMES_BLOCKLIST:
                return normalized_hint
    
    if merchant_hint in ("Petropar", "Shell", "Copetrol", "Enex", "Stock", "Vernier", "Western Union"):
        return merchant_hint
    
    patterns = [
        r"(shell|copetrol|petropar|petrobras|enex|fp|stock|superseis|carrefour|walmart|vernier)(?:\s+\w+)?",
        r"subway(?:\s+\w+)?",
        r"burger\s*king(?:\s+\w+)?",
        r"alula(?:\s+\w+)?",
        r"bar\s*nacional",
        r"farmacenter",
        r"western\s*union",
        r"palemar",
        r"el\s*legado",
        r"dba(?:\s+club)?",
        r"ccp(?:\s+\w+)?",
        r"upays?",
        r"goles(?:\s+\w+)?",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:\d+\s*%)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, block, re.I)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2:
                normalized = normalize_merchant_name(name)
                if normalized and _is_valid_merchant_name(normalized):
                    if normalized.lower() not in BANK_NAMES_BLOCKLIST:
                        return normalized
    
    lines = block.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) > 2 and len(line) < 40:
            normalized = normalize_merchant_name(line)
            if normalized and _is_valid_merchant_name(normalized):
                line_lower = line.lower()
                if not any(w in line_lower for w in GENERIC_WORDS):
                    if not any(fake in line_lower for fake in ["reintegro", "descuento", "beneficio", "promocion", "vigencia", "tope"]):
                        if normalized.lower() not in BANK_NAMES_BLOCKLIST:
                            return normalized
    
    return None


def _extract_discount_percent(text: str) -> Optional[Decimal]:
    patterns = [
        r"(\d{1,3})\s*%",
        r"(\d{1,3})\s*porciento",
        r"dto\s*(\d{1,3})",
        r"(\d{1,3})%\s*de\s*(reintegro|descuento)",
        r"(\d+)\s*%",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            pct = int(match.group(1))
            if 1 <= pct <= 100:
                return Decimal(pct)
    
    return None


def _extract_installment_count(text: str) -> Optional[int]:
    match = re.search(r"(\d{1,2})\s*cuotas?", text, re.I)
    if match:
        return int(match.group(1))
    return None


def _extract_benefit_type(text: str) -> Optional[str]:
    lower = text.lower()
    
    if "reintegro" in lower:
        return "reintegro"
    if "descuento" in lower or "dto" in lower:
        return "descuento"
    if "cuota" in lower:
        return "cuotas"
    
    return None


def _extract_category_from_block(block: str, category_hint: str = None) -> Optional[str]:
    if category_hint and category_hint not in ("General", "None", None, ""):
        return category_hint
    
    lower = block.lower()
    
    category_keywords = [
        (["combustible", "combustibles", "estacion", "shell", "petro", "nafta", "diesel", "copetrol", "enex", "petropar", "石化", "estaciones"], "Combustible"),
        (["supermercado", "supermercados", "stock", "superseis", "carrefour", "arete", "biggie", "prioridad", "supermax"], "Supermercados"),
        (["gastr", "restaur", "bar ", "pizza", "sushi", "comida", "burger", "subway", "café", "mcdonald", "kfc", "helados", "panc", "postres"], "Gastronomía"),
        (["ropa", "indumentaria", "moda", "tiendas", "tienda", "libreria", "librerías", "colegio", "lector", "libros", "educaci"], "Educación"),
        (["tecnologia", "celular", "tech", "electro", "plataformas", "ecommerce", "tienda online", "digital"], "Tecnología"),
        (["farmacia", "salud", "farmacenter", "medicamentos", "simples", "farma"], "Salud"),
        (["belleza", "spa", "peluqu", "cosmét"], "Belleza"),
        (["hogar", "muebleria", "decor", "interior"], "Hogar"),
        (["viaje", "hotel", "turismo", "agencia", "vuelos"], "Viajes"),
        (["entretenimiento", "entretenimi", "cine", "espectacul", "concierto"], "Entretenimiento"),
        (["ropa", "tiendas", "tienda", "indumentaria"], "Indumentaria"),
    ]
    
    for keywords, category in category_keywords:
        if any(kw in lower for kw in keywords):
            return category
    
    return "General"


def _extract_valid_days(text: str) -> List[str]:
    found_days = set()
    lower = text.lower()
    
    for day, aliases in DAY_MAP.items():
        for alias in aliases:
            if alias in lower:
                found_days.add(day)
    
    return sorted(list(found_days))


def _extract_dates(text: str):
    valid_from = None
    valid_to = None
    if not text:
        return valid_from, valid_to
    
    text_lower = text.lower()
    
    year_match = re.search(r"20\d{2}", text)
    year = 2026
    if year_match:
        try:
            year = int(year_match.group(0))
        except:
            pass
    
    month_names = {"ene","en","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic",
                   "enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"}
    
    patterns = [
        r"(?:desde|desdel)\s*(?:el\s*)?(\d{1,2})\s*de\s*(\w+)\s*(?:hasta|al)\s*(?:el\s*)?(\d{1,2})\s*de\s*(\w+)",
        r"(\d{1,2})\s*de\s*(\w+)\s*(?:hasta|al)\s*(\d{1,2})\s*de\s*(\w+)",
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:al|-)\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
        r"v[áa]lido\s*(?:del\s*)?(\d{1,2})\s*(?:de\s*)?(?:al\s*)?(\d{1,2})\s*de\s*(\w+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            try:
                g = match.groups()
                if len(g) == 4:
                    d1_str, m1_name, d2_str, m2_name = g
                    if d1_str and m1_name in month_names and d2_str and m2_name in month_names:
                        d1 = int(d1_str)
                        d2 = int(d2_str)
                        m1 = _MONTH_MAP.get(m1_name, 1)
                        m2 = _MONTH_MAP.get(m2_name, 12)
                        if 1 <= d1 <= 31 and 1 <= d2 <= 31:
                            valid_from = date(year, m1, d1)
                            valid_to = date(year, m2, d2)
                            break
                elif len(g) == 3:
                    d1_str, d2_str, m2_name = g
                    if d1_str and d2_str and m2_name in month_names:
                        d1 = int(d1_str)
                        d2 = int(d2_str)
                        m2 = _MONTH_MAP.get(m2_name, 12)
                        if 1 <= d1 <= 31 and 1 <= d2 <= 31:
                            valid_from = date(year, m2, d1)
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


def _extract_cap(text: str) -> Optional[Decimal]:
    if not text:
        return None
    text_lower = text.lower()
    
    context_kw = ["tope", "compra", "reintegro", "máximo", "maximo", "gs", "límite", "monto"]
    if not any(kw in text_lower for kw in context_kw):
        return None
    
    patterns = [
        r"tope[:\s.]*([\d.]+)",
        r"Gs\.?\s*([\d,]+)",
        r"hasta\s*Gs\.?\s*([\d,]+)",
        r"cap[:\s]*([\d,]+)",
        r"maximo[:\s.]*([\d,]+)",
        r"máximo[:\s.]*([\d,]+)",
        r"reintegro\s*(máximo|maximo)?[:\s.]*([\d.]+)",
        r"compra\s*(máximo|maximo)?[:\s.]*([\d,]+)",
        r"([\d.]{3,})\s*(?:Gs|gs|guaraníes|guaranies)",
        r"([\d.]{2,})\s*(?:millones|millón)\s*(?:de\s+)?(?:Gs|gs)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            g1 = match.group(1)
            if g1 is None:
                continue
            try:
                amount_str = g1.replace(".", "").replace(",", "")
            except Exception:
                continue
            if amount_str.isdigit() and len(amount_str) >= 3:
                try:
                    val = int(amount_str)
                    if val >= 5000:
                        return Decimal(val)
                    elif val >= 1000 and any(kw in text_lower for kw in context_kw):
                        return Decimal(val)
                except Exception:
                    pass
    
    millions_match = re.search(r"(\d+(?:,\d+)?)\s*(millones|millón)\s*(?:de\s+)?(?:Gs|gs|guaraníes)?", text, re.I)
    if millions_match:
        try:
            gm = millions_match.group(1)
            if gm:
                millions = float(gm.replace(",", "."))
                if millions >= 0.5:
                    return Decimal(int(millions * 1000000))
        except:
            pass
    
    return None


def _extract_payment_method(text: str) -> Optional[str]:
    patterns = [
        (r"visa", "Visa"),
        (r"mastercard", "Mastercard"),
        (r"credicard", "Credicard"),
        (r"american\s*express", "American Express"),
        (r"debito", "Débito"),
        (r"cuenta\s*digital", "Cuenta Digital"),
    ]
    
    for pattern, method in patterns:
        if re.search(pattern, text, re.I):
            return method
    
    return None


def _extract_emblem(text: str) -> Optional[str]:
    lower = text.lower()
    
    for emblem in VALID_EMBLEMS:
        if emblem in lower:
            return emblem.title()
    
    return None


def _extract_conditions(text: str) -> Optional[str]:
    patterns = [
        r"condicione[s]:?\s*([^\n]+)",
        r"términos?[,\s]*([^\n]+)",
        r"aplica[,\s]*([^\n]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip()[:200]
    
    return None


class PDFParserResult:
    def __init__(self):
        self.pdf_found = False
        self.pdf_urls: List[str] = []
        self.pdf_parse_success = False
        self.pdf_promos_extracted = 0
        self.html_promos_extracted = 0
        self.rejected_generic = 0
        self.final_saved = 0
        self.source_selected = "unknown"


def discover_pdfs_from_page(page, base_url: str) -> List[str]:
    pdf_links = []
    
    if not page:
        return pdf_links
    
    selectors = [
        'a[href$=".pdf"]',
        'a[href*="pdf"]',
        'a[href*="catalogo"]',
        'a[href*="catalog"]',
        'a[href*="promo"]',
        'a[href*="beneficio"]',
    ]
    
    for selector in selectors:
        try:
            els = page.locator(selector).all()
            for el in els:
                href = el.get_attribute("href")
                if href:
                    full_url = urljoin(base_url, href) if not href.startswith("http") else href
                    if full_url not in pdf_links:
                        pdf_links.append(full_url)
        except Exception:
            pass
    
    return pdf_links