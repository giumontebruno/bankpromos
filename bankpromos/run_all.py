from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from bankpromos.core.deduper import dedupe_promotions
from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import normalize_promotion
from bankpromos.core.scoring import score_promotion
from bankpromos.pdf_parser import extract_pdf_text, parse_promotions_from_pdf
from bankpromos.scrapers import get_scraper
from bankpromos.scrapers.base_public import ScraperDiagnostics


SUPPORTED_BANKS = ["py_sudameris", "py_ueno", "py_itau", "py_continental", "py_bnf"]


def _discover_local_pdfs(pdfs_dir: str = "data/pdfs") -> List[Path]:
    if not Path(pdfs_dir).exists():
        return []
    return list(Path(pdfs_dir).glob("*.pdf"))


def _extract_bank_and_hints(filename: str, text_sample: str = "") -> Tuple[str, Optional[str], Optional[str]]:
    fn_lower = filename.lower()
    text_lower = (text_sample or "").lower()
    
    bank_id = "unknown"
    merchant_hint = None
    category_hint = None
    
    if "ueno" in fn_lower:
        bank_id = "ueno"
        merchant_hint = "Ueno"
    elif "itau" in fn_lower:
        bank_id = "itau"
    elif "sudameris" in fn_lower:
        bank_id = "sudameris"
    elif "continental" in fn_lower:
        bank_id = "continental"
    elif "bnf" in fn_lower:
        bank_id = "bnf"
    elif "sudameris" in text_lower:
        bank_id = "sudameris"
    elif "ueno" in text_lower:
        bank_id = "ueno"
        merchant_hint = "Ueno"
    elif "itau" in text_lower:
        bank_id = "itau"
    elif "continental" in text_lower or "banco continental" in text_lower:
        bank_id = "continental"
    elif "bnf" in text_lower:
        bank_id = "bnf"
    
    if "combustible" in fn_lower:
        category_hint = "Combustible"
    elif "supermercado" in fn_lower:
        category_hint = "Supermercados"
    elif "gastronomi" in fn_lower:
        category_hint = "Gastronomia"
    elif "entretenimiento" in fn_lower:
        category_hint = "Entretenimiento"
    elif "viaje" in fn_lower:
        category_hint = "Viajes"
    elif "indumentaria" in fn_lower:
        category_hint = "Indumentaria"
    elif "belleza" in fn_lower:
        category_hint = "Belleza"
    elif "tbk" in fn_lower:
        category_hint = "Tecnologia"
    elif "black" in fn_lower:
        category_hint = "General"
    
    return bank_id, merchant_hint, category_hint


def run_pdf_extraction(pdfs_dir: str = "data/pdfs") -> List[PromotionModel]:
    pdf_files = _discover_local_pdfs(pdfs_dir)
    
    if not pdf_files:
        return []
    
    all_promos: List[PromotionModel] = []
    
    for pdf_path in pdf_files:
        try:
            text = extract_pdf_text(str(pdf_path))
            if not text or len(text.strip()) < 50:
                continue
            
            text_sample = text[:500]
            bank_id, merchant_hint, category_hint = _extract_bank_and_hints(pdf_path.name, text_sample)
            
            if bank_id == "unknown":
                detected_bank = None
                text_lower = text_sample.lower()
                if "sudameris" in text_lower:
                    detected_bank = "sudameris"
                elif "ueno" in text_lower:
                    detected_bank = "ueno"
                    merchant_hint = "Ueno"
                elif "itau" in text_lower:
                    detected_bank = "itau"
                elif "continental" in text_lower or "banco continental" in text_lower:
                    detected_bank = "continental"
                elif "bnf" in text_lower:
                    detected_bank = "bnf"
                if detected_bank:
                    bank_id = detected_bank
            
            if bank_id == "unknown":
                continue
            
            promos = parse_promotions_from_pdf(
                text,
                bank_id,
                source_url=str(pdf_path),
                category_hint=category_hint,
                merchant_hint=merchant_hint,
            )
            
            for promo in promos:
                promo.raw_data["source_type"] = "pdf_local"
                promo.raw_data["pdf_filename"] = pdf_path.name
            
            all_promos.extend(promos)
        except Exception as e:
            continue
    
    return all_promos


def run_scraper(bank_id: str, debug_mode: bool = False) -> Tuple[List[PromotionModel], Optional[str]]:
    if bank_id not in SUPPORTED_BANKS:
        return [], f"Unsupported bank: {bank_id}"

    try:
        scraper = get_scraper(bank_id, debug_mode=debug_mode)
        promos = scraper.scrape()
        return promos, None
    except Exception as e:
        return [], str(e)


def run_scraper_with_diagnostics(bank_id: str, debug_mode: bool = True) -> Tuple[List[PromotionModel], Optional[ScraperDiagnostics], Optional[str]]:
    if bank_id not in SUPPORTED_BANKS:
        return [], None, f"Unsupported bank: {bank_id}"

    try:
        scraper = get_scraper(bank_id, debug_mode=debug_mode)
        promos = scraper.scrape()
        diag = scraper.get_diagnostics()
        return promos, diag, None
    except Exception as e:
        return [], None, str(e)


def run_all_scrapers(
    bank_ids: Optional[List[str]] = None,
    debug_mode: bool = False,
) -> Tuple[List[PromotionModel], Dict[str, str]]:
    if bank_ids is None:
        bank_ids = SUPPORTED_BANKS

    bank_ids = [b for b in bank_ids if b in SUPPORTED_BANKS]
    if not bank_ids:
        bank_ids = SUPPORTED_BANKS

    all_promos: List[PromotionModel] = []
    errors: Dict[str, str] = {}

    for bank_id in bank_ids:
        print(f"Running scraper: {bank_id}")
        promos, error = run_scraper(bank_id, debug_mode=debug_mode)

        if error:
            print(f"  Error: {error}")
            errors[bank_id] = error
        else:
            print(f"  Found {len(promos)} promotions")
            all_promos.extend(promos)

    if not all_promos:
        return [], {"sources": {"scraped": 0, "pdf": 0, "curated": 0}, "errors": errors}

    print(f"\nNormalizing {len(all_promos)} promotions...")
    normalized = [normalize_promotion(p) for p in all_promos]

    print(f"Deduplicating...")
    deduped = dedupe_promotions(normalized)

    print(f"Scoring...")
    scored = [score_promotion(p) for p in deduped]

    print(f"\nFinal: {len(scored)} unique promotions")
    return scored, {"sources": {"scraped": len(all_promos), "pdf": 0, "final": len(scored)}, "errors": errors}


def run_collection_pipeline(
    include_scrapers: bool = True,
    include_pdfs: bool = True,
    bank_ids: Optional[List[str]] = None,
    pdfs_dir: str = "data/pdfs",
    debug_mode: bool = False,
) -> Tuple[List[PromotionModel], Dict[str, Any]]:
    source_counts: Dict[str, int] = {
        "scraped": 0,
        "pdf": 0,
        "curated": 0,
    }
    
    all_promos: List[PromotionModel] = []
    errors: Dict[str, str] = {}
    
    if include_scrapers:
        print("=" * 50)
        print("Running scrapers...")
        print("=" * 50)
        
        if bank_ids is None:
            bank_ids = SUPPORTED_BANKS
        
        for bank_id in bank_ids:
            if bank_id not in SUPPORTED_BANKS:
                continue
            
            print(f"  {bank_id}: ", end="", flush=True)
            promos, error = run_scraper(bank_id, debug_mode=debug_mode)
            
            if error:
                print(f"ERROR - {error}")
                errors[bank_id] = error
            else:
                print(f"{len(promos)} promos")
                source_counts["scraped"] += len(promos)
                for promo in promos:
                    promo.raw_data["source_type"] = "scraped"
                all_promos.extend(promos)
    
    if include_pdfs:
        print("=" * 50)
        print("Extracting from PDFs...")
        print("=" * 50)
        
        pdf_promos = run_pdf_extraction(pdfs_dir)
        print(f"  Found {len(pdf_promos)} promos from PDFs")
        source_counts["pdf"] = len(pdf_promos)
        all_promos.extend(pdf_promos)
    
    if not all_promos:
        return [], {"sources": source_counts, "errors": errors}
    
    print("=" * 50)
    print("Normalizing...")
    normalized = [normalize_promotion(p) for p in all_promos]
    
    print("Deduplicating...")
    deduped = dedupe_promotions(normalized)
    
    pdf_count = sum(1 for p in deduped if p.raw_data.get("source_type") == "pdf_local")
    source_counts["curated"] = pdf_count
    
    print("Scoring...")
    scored = [score_promotion(p) for p in deduped]
    
    source_counts["final"] = len(scored)
    
    print("=" * 50)
    print(f"Final: {len(scored)} unique promotions")
    print(f"  Scraped: {source_counts['scraped']}")
    print(f"  PDF: {source_counts['pdf']}")
    print(f"  Curated: {source_counts['curated']}")
    print("=" * 50)
    
    return scored, {"sources": source_counts, "errors": errors}