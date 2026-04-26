import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

from bankpromos.pdf_parser import (
    extract_pdf_text,
    split_pdf_into_blocks,
    parse_promotions_from_pdf,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PDF_DIR = Path("data/pdfs")


def debug_pdf(pdf_path: Path) -> dict:
    print(f"\n{'='*60}")
    print(f"PDF: {pdf_path.name}")
    print(f"{'='*60}")
    
    text = extract_pdf_text(str(pdf_path))
    if not text:
        print("ERROR: Could not extract text")
        return {"error": "no text"}
    
    text_len = len(text)
    print(f"Text length: {text_len} chars")
    
    filename_lower = pdf_path.name.lower()
    category_hint = None
    merchant_hint = None
    
    cat_map = {
        "combustibles": "Combustible", "combustible": "Combustible",
        "supermercados": "Supermercados", "supermercado": "Supermercados",
        "gastronomia": "Gastronomía", "gastronomía": "Gastronomía",
        "indumentaria": "Indumentaria",
        "tecnologia": "Tecnología", "tecnología": "Tecnología",
    }
    for kw, cat in cat_map.items():
        if kw in filename_lower:
            category_hint = cat
            break
    
    emblem_map = {"shell": "Shell", "copetrol": "Copetrol", "petropar": "Petropar", 
                "petrobras": "Petrobras", "enex": "Enex"}
    for emb, name in emblem_map.items():
        if emb in filename_lower:
            merchant_hint = name
            if not category_hint:
                category_hint = "Combustible"
            break
    
    if "ueno" in filename_lower:
        merchant_hint = "Ueno"
    if "itau" in filename_lower:
        merchant_hint = "Itaú"
    
    print(f"Category hint: {category_hint}")
    print(f"Merchant hint: {merchant_hint}")
    
    blocks = split_pdf_into_blocks(text)
    block_count = len(blocks)
    print(f"Blocks found: {block_count}")
    
    print(f"\n--- First 5 blocks (raw) ---")
    for i, block in enumerate(blocks[:5]):
        safe = block[:120].encode('ascii', errors='replace').decode('ascii')
        print(f"Block {i}: {safe}...")
    
    bank_id = "py_ueno"
    promos = parse_promotions_from_pdf(
        text, bank_id, str(pdf_path),
        category_hint=category_hint,
        merchant_hint=merchant_hint
    )
    promo_count = len(promos)
    print(f"\nExtracted promotions: {promo_count}")
    
    print(f"\n--- Extracted promotions ---")
    for i, p in enumerate(promos[:10]):
        print(f"\nPromo {i + 1}:")
        print(f"  merchant: {p.merchant_name}")
        print(f"  discount: {p.discount_percent}")
        print(f"  category: {p.category}")
        print(f"  valid_days: {p.valid_days}")
        print(f"  cap: {p.cap_amount}")
        print(f"  benefit: {p.benefit_type}")
        print(f"  installment: {p.installment_count}")
        rt = (p.raw_text or '')[:80].encode('ascii', errors='replace').decode('ascii')
        print(f"  raw_text: {rt}...")
    
    if not promos:
        print("\nNo promotions extracted - check block splitting or extraction logic")
    
    return {
        "file": pdf_path.name,
        "text_len": text_len,
        "blocks": block_count,
        "promos": promo_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Debug PDF extraction")
    parser.add_argument("file", nargs="?", help="Specific PDF file in data/pdfs/")
    args = parser.parse_args()
    
    if not PDF_DIR.exists():
        print(f"Creating {PDF_DIR}")
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Please add PDF files to {PDF_DIR}")
        return
    
    if args.file and args.file != "pdf-debug":
        pdf_path = PDF_DIR / args.file
        if not pdf_path.exists():
            print(f"File not found: {pdf_path}")
            return
        pdf_files = [pdf_path]
    else:
        files = os.listdir(str(PDF_DIR))
        pdf_files = [PDF_DIR / f for f in files if f.lower().endswith(".pdf")]
        pdf_files = sorted(pdf_files)
    
    if not pdf_files:
        print(f"No PDFs found in {PDF_DIR}")
        return
    
    print(f"Found {len(pdf_files)} PDF(s)")
    
    total_stats = {
        "files": 0,
        "total_text": 0,
        "total_blocks": 0,
        "total_promos": 0,
    }
    
    for pdf_path in pdf_files:
        if not pdf_path.exists():
            print(f"Skipping missing: {pdf_path}")
            continue
        
        file_size = pdf_path.stat().st_size
        total_stats["files"] += 1
        
        print(f"\n[{total_stats['files']}/{len(pdf_files)}] Processing: {pdf_path.name} ({file_size} bytes)")
        
        try:
            result = debug_pdf(pdf_path)
            
            if "error" not in result:
                total_stats["total_text"] += result.get("text_len", 0)
                total_stats["total_blocks"] += result.get("blocks", 0)
                total_stats["total_promos"] += result.get("promos", 0)
        except Exception as e:
            print(f"ERROR processing {pdf_path.name}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Files processed: {total_stats['files']}")
    print(f"Total text: {total_stats['total_text']} chars")
    print(f"Total blocks: {total_stats['total_blocks']}")
    print(f"Total promos: {total_stats['total_promos']}")
    
    if total_stats["files"] > 1:
        print(f"\nAvg blocks/file: {total_stats['total_blocks'] / total_stats['files']:.1f}")
        print(f"Avg promos/file: {total_stats['total_promos'] / total_stats['files']:.1f}")


if __name__ == "__main__":
    main()