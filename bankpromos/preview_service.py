import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import fitz

logger = logging.getLogger(__name__)

PREVIEWS_DIR = Path("data/previews")
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)


def _get_item_id(pattern_key: str) -> str:
    hash_obj = hashlib.md5(pattern_key.encode(), usedforsecurity=False)
    return hash_obj.hexdigest()[:12]


def generate_pdf_preview(
    pdf_path: str,
    page: int = 0,
    item_id: Optional[str] = None,
) -> Optional[str]:
    if item_id is None:
        item_id = _get_item_id(pdf_path)
    
    output_path = PREVIEWS_DIR / f"{item_id}.png"
    
    if output_path.exists():
        logger.debug(f"Preview already exists: {output_path}")
        return f"/previews/{item_id}.png"
    
    try:
        doc = fitz.open(pdf_path)
        if page >= len(doc):
            logger.warning(f"Page {page} out of range for {pdf_path}")
            doc.close()
            return None
        
        pix = doc[page].get_pixmap(matrix=fitz.Matrix(2, 2))
        pix.save(str(output_path))
        doc.close()
        
        logger.info(f"Generated preview: {output_path}")
        return f"/previews/{item_id}.png"
    
    except Exception as e:
        logger.error(f"Failed to generate preview for {pdf_path}: {e}")
        return None


def generate_preview_for_item(
    pattern_key: str,
    pdf_path: str,
    page: int = 0,
) -> Optional[str]:
    item_id = _get_item_id(pattern_key)
    return generate_pdf_preview(pdf_path, page, item_id)


def get_preview_status() -> dict:
    previews_dir_exists = PREVIEWS_DIR.exists()
    
    previews = []
    if previews_dir_exists:
        previews = list(PREVIEWS_DIR.glob("*.png"))
    
    return {
        "previews_dir_exists": previews_dir_exists,
        "preview_count": len(previews),
        "sample_files": [p.name for p in previews[:5]],
    }