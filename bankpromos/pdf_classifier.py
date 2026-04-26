import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PDFS_DIR = "data/pdfs"

BANK_PATTERNS = {
    "ueno": [
        r"ueno",
        r"ueno\s*black",
        r"promocion.*ueno",
        r"beneficio.*ueno",
        r"byc.*ueno",
        r"^ueno",
        r"ueno\s*abril",
        r"ueno\s*black",
    ],
    "sudameris": [
        r"sudameris",
        r"sudameris\.com\.py",
        r"byc.*sudameris",
    ],
    "continental": [
        r"continental",
        r"guia_de_beneficios",
        r"guia.*beneficios",
        r"bancontinental",
    ],
    "itau": [
        r"itau",
        r"itáu",
    ],
    "bnf": [
        r"bnf",
    ],
}

CATEGORY_PATTERNS = {
    "Combustible": [
        r"combustible",
        r"combustibles",
        r"petropar",
        r"shell",
        r"copetrol",
        r"enex",
    ],
    "Supermercados": [
        r"supermercado",
        r"supermercados",
    ],
    "Gastronomía": [
        r"gastronomia",
        r"gastronom[ií]a",
        r"restaurante",
        r"bar",
    ],
    "Indumentaria": [
        r"tiendas",
        r"indumentaria",
        r"ropa",
        r"black.*tiendas",
    ],
    "Tecnología": [
        r"tecnolog",
        r"tecnolog",
        r"electro",
    ],
    "Viajes": [
        r"viaje",
        r"viajes",
        r"hotel",
        r"agencia",
    ],
    "Entretenimiento": [
        r"entretenimiento",
        r"entretenimiento",
        r"entretenimi",
    ],
    "Belleza": [
        r"belleza",
        r"spa",
    ],
    "Salud": [
        r"salud",
        r"farmacia",
        r"farma",
    ],
}

MERCHANT_HINTS = {
    "petropar": "Petropar",
    "copetrol": "Copetrol",
    "shell": "Shell",
    "enex": "Enex",
    "vernier": "Vernier",
    "western union": "Western Union",
    "alula": "Alula Hotel",
    "subway": "Subway",
    "burger king": "Burger King",
    "farmacenter": "Farmacenter",
    "bar nacional": "Bar Nacional",
    "el legado": "El Legado",
    "patio colonial": "Patio Colonial",
    "chaval": "Chaval",
    "libreria la plaza": "Librería La Plaza",
    "el lector": "El Lector",
    "beauty bar": "Beauty Bar",
    "planet toys": "Planet Toys",
    "goles": "Goles",
    "palemar": "Fería Palemar",
    "dba": "DBA Club",
    "ccp": "CCP",
    "upys": "UPYs",
    "alma": "Alma Hotel",
}

REJECT_PATTERNS = [
    r"^test\.pdf$",
    r"corporate",
    r"governance",
    r"presencia del 100%",
    r"reintegro del 100%",
    r"plazo de acreditaci",
    r"el reintegro del",
    r"un descuento del",
]


def classify_pdf_file(filename: str, text: str = "") -> Tuple[Optional[str], Optional[str], Optional[str]]:
    filename_lower = filename.lower()
    text_lower = text.lower()[:5000] if text else ""
    
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, text_lower):
            return None, None, None
    
    bank = None
    for b, patterns in BANK_PATTERNS.items():
        for p in patterns:
            if re.search(p, filename_lower) or re.search(p, text_lower):
                bank = b
                break
        if bank:
            break
    
    if not bank:
        if "beneficio" in filename_lower and "ueno" not in filename_lower:
            bank = "ueno"
        elif "promocion" in filename_lower:
            bank = "ueno"
    
    category = None
    for c, patterns in CATEGORY_PATTERNS.items():
        for p in patterns:
            if re.search(p, filename_lower):
                category = c
                break
        if category:
            break
    
    merchant = None
    for hint, merch in MERCHANT_HINTS.items():
        if hint in filename_lower:
            merchant = merch
            break
    
    if not merchant and "black" in filename_lower and "tiendas" in filename_lower:
        merchant = "BLACK Tiendas"
    
    return bank, category, merchant


def get_pdf_sources() -> Dict[str, List[Dict]]:
    pdfs_dir = Path(PDFS_DIR)
    sources_by_bank = {
        "ueno": [],
        "sudameris": [],
        "continental": [],
        "itau": [],
        "bnf": [],
    }
    
    if not pdfs_dir.exists():
        return sources_by_bank
    
    files = sorted(pdfs_dir.glob("*.pdf"))
    
    for pdf_file in files:
        try:
            if pdf_file.stat().st_size < 100:
                continue
        except:
            continue
        
        try:
            from bankpromos.pdf_parser import extract_pdf_text
            text = extract_pdf_text(str(pdf_file))
        except:
            text = ""
        
        bank, category, merchant = classify_pdf_file(pdf_file.name, text)
        
        if bank:
            sources_by_bank[bank].append({
                "file": str(pdf_file),
                "filename": pdf_file.name,
                "size": pdf_file.stat().st_size,
                "category_hint": category,
                "merchant_hint": merchant,
                "bank": bank,
            })
    
    return sources_by_bank


def get_sources_for_bank(bank: str) -> List[Dict]:
    all_sources = get_pdf_sources()
    return all_sources.get(bank, [])


if __name__ == "__main__":
    sources = get_pdf_sources()
    print("PDF Sources by Bank:")
    for bank, srcs in sources.items():
        print(f"  {bank}: {len(srcs)} files")
        for s in srcs[:3]:
            print(f"    - {s['filename']} ({s.get('category_hint')})")