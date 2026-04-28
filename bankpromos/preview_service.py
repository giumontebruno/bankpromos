import hashlib
import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

logger = logging.getLogger(__name__)

PREVIEWS_DIR = Path("data/previews")
CROPS_DIR = Path("data/previews/crops")
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
CROPS_DIR.mkdir(parents=True, exist_ok=True)


def _get_item_id(pattern_key: str) -> str:
    hash_obj = hashlib.md5(pattern_key.encode(), usedforsecurity=False)
    return hash_obj.hexdigest()[:12]


def _normalize_text(txt: str) -> str:
    if not txt:
        return ""
    txt = txt.lower().strip()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def _find_text_in_pdf(pdf_path: str, search_text: str, max_pages: int = 10) -> Optional[Dict[str, Any]]:
    if not search_text or len(search_text) < 3:
        return None
    
    search_normalized = _normalize_text(search_text)
    
    try:
        doc = fitz.open(pdf_path)
        num_pages = min(len(doc), max_pages)
        
        for page_num in range(num_pages):
            page = doc[page_num]
            
            text = page.get_text()
            if not text:
                continue
            
            text_normalized = _normalize_text(text)
            
            if search_normalized in text_normalized:
                blocks = page.get_text("dict")
                
                for block in blocks.get("blocks", []):
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            try:
                                block_text += str(span.get("text", ""))
                            except:
                                pass
                    
                    block_normalized = _normalize_text(block_text)
                    
                    if search_normalized in block_normalized:
                        bbox = block.get("bbox")
                        if bbox:
                            doc.close()
                            return {
                                "page": page_num,
                                "bbox": bbox,
                                "block_text": block_text.strip()[:100],
                            }
                
                bbox = page.search_for(search_text[:50])
                if bbox:
                    doc.close()
                    return {
                        "page": page_num,
                        "bbox": bbox[0] if bbox else None,
                        "block_text": search_text[:100],
                    }
        
        doc.close()
        
    except Exception as e:
        logger.error(f"Error searching text in PDF: {e}")
    
    return None


def _get_bbox_for_field(pdf_path: str, field_type: str, value: str, page_num: int = 0) -> Optional[Dict[str, Any]]:
    if not value or len(value) < 2:
        return None
    
    try:
        doc = fitz.open(pdf_path)
        
        if page_num >= len(doc):
            doc.close()
            return None
        
        page = doc[page_num]
        
        search_term = value
        if field_type == "discount":
            search_term = f"{value}%"
        elif field_type == "day":
            days = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
            for d in days:
                if d in value.lower():
                    search_term = d
                    break
        elif field_type == "cap":
            search_term = str(value)
        
        results = page.search_for(search_term[:30])
        
        if results:
            bbox = results[0]
            doc.close()
            return {
                "bbox": bbox,
                "source": "pdf_bbox",
                "confidence": 0.95,
            }
        
        doc.close()
        
    except Exception as e:
        logger.error(f"Error getting bbox for {field_type}: {e}")
    
    return None


def _convert_bbox_to_relative(bbox: Tuple, page_width: float, page_height: float) -> Dict[str, float]:
    x0, y0, x1, y1 = bbox
    
    return {
        "x": x0 / page_width,
        "y": y0 / page_height,
        "w": (x1 - x0) / page_width,
        "h": (y1 - y0) / page_height,
    }


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


def generate_crop_preview(
    pdf_path: str,
    page: int = 0,
    bbox: Optional[Tuple] = None,
    item_id: Optional[str] = None,
    padding: float = 50,
) -> Optional[str]:
    if item_id is None:
        item_id = _get_item_id(pdf_path)
    
    crop_path = CROPS_DIR / f"{item_id}.png"
    
    if crop_path.exists():
        return f"/previews/crops/{item_id}.png"
    
    try:
        doc = fitz.open(pdf_path)
        
        if page >= len(doc):
            doc.close()
            return None
        
        page_obj = doc[page]
        page_width = page_obj.rect.width
        page_height = page_obj.rect.height
        
        if bbox:
            x0, y0, x1, y1 = bbox
            x0 = max(0, x0 - padding)
            y0 = max(0, y0 - padding)
            x1 = min(page_width, x1 + padding)
            y1 = min(page_height, y1 + padding)
            clip_rect = fitz.Rect(x0, y0, x1, y1)
        else:
            clip_rect = None
        
        pix = page_obj.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip_rect)
        pix.save(str(crop_path))
        doc.close()
        
        logger.info(f"Generated crop: {crop_path}")
        return f"/previews/crops/{item_id}.png"
    
    except Exception as e:
        logger.error(f"Failed to generate crop for {pdf_path}: {e}")
        return None


def extract_visual_regions_from_pdf(
    pdf_path: str,
    page: int,
    detected_text: str,
    detected_merchant: str,
    detected_discount: Any,
    detected_days: List[str],
    detected_cap: Any,
) -> List[Dict[str, Any]]:
    regions = []
    
    try:
        doc = fitz.open(pdf_path)
        
        if page >= len(doc):
            doc.close()
            return _generate_heuristic_regions(detected_merchant, detected_discount, detected_days, detected_cap)
        
        page_obj = doc[page]
        page_width = page_obj.rect.width
        page_height = page_obj.rect.height
        
        text = page_obj.get_text()
        text_lower = text.lower()
        
        if detected_merchant and len(detected_merchant) > 2:
            bbox_info = _get_bbox_for_field(pdf_path, "merchant", detected_merchant, page)
            if bbox_info:
                rel = _convert_bbox_to_relative(bbox_info["bbox"], page_width, page_height)
                regions.append({
                    "field": "merchant",
                    "label": "Comercio",
                    "value": detected_merchant,
                    "x": rel["x"],
                    "y": rel["y"],
                    "w": rel["w"],
                    "h": rel["h"],
                    "confidence": 0.95,
                    "source": "pdf_bbox",
                })
        
        if detected_discount:
            discount_val = str(detected_discount)
            bbox_info = _get_bbox_for_field(pdf_path, "discount", discount_val, page)
            if bbox_info:
                rel = _convert_bbox_to_relative(bbox_info["bbox"], page_width, page_height)
                regions.append({
                    "field": "discount",
                    "label": "Descuento",
                    "value": f"{discount_val}%",
                    "x": rel["x"],
                    "y": rel["y"],
                    "w": rel["w"],
                    "h": rel["h"],
                    "confidence": 0.95,
                    "source": "pdf_bbox",
                })
        
        if detected_days and len(detected_days) > 0:
            day_text = detected_days[0].lower()
            bbox_info = _get_bbox_for_field(pdf_path, "day", day_text, page)
            if bbox_info:
                rel = _convert_bbox_to_relative(bbox_info["bbox"], page_width, page_height)
                regions.append({
                    "field": "day",
                    "label": "Día",
                    "value": ", ".join(detected_days[:3]),
                    "x": rel["x"],
                    "y": rel["y"],
                    "w": rel["w"],
                    "h": rel["h"],
                    "confidence": 0.95,
                    "source": "pdf_bbox",
                })
        
        if detected_cap:
            cap_val = str(detected_cap)
            bbox_info = _get_bbox_for_field(pdf_path, "cap", cap_val, page)
            if bbox_info:
                rel = _convert_bbox_to_relative(bbox_info["bbox"], page_width, page_height)
                regions.append({
                    "field": "cap",
                    "label": "Tope",
                    "value": cap_val,
                    "x": rel["x"],
                    "y": rel["y"],
                    "w": rel["w"],
                    "h": rel["h"],
                    "confidence": 0.95,
                    "source": "pdf_bbox",
                })
        
        if "cuota" in text_lower:
            bbox_info = _get_bbox_for_field(pdf_path, "conditions", "cuota", page)
            if bbox_info:
                rel = _convert_bbox_to_relative(bbox_info["bbox"], page_width, page_height)
                regions.append({
                    "field": "conditions",
                    "label": "Condiciones",
                    "value": "cuotas",
                    "x": rel["x"],
                    "y": rel["y"],
                    "w": rel["w"],
                    "h": rel["h"],
                    "confidence": 0.95,
                    "source": "pdf_bbox",
                })
        
        doc.close()
        
        if not regions:
            return _generate_heuristic_regions(detected_merchant, detected_discount, detected_days, detected_cap)
        
        return regions
        
    except Exception as e:
        logger.error(f"Error extracting visual regions: {e}")
        return _generate_heuristic_regions(detected_merchant, detected_discount, detected_days, detected_cap)


def _generate_heuristic_regions(
    detected_merchant: str,
    detected_discount: Any,
    detected_days: List[str],
    detected_cap: Any,
) -> List[Dict[str, Any]]:
    regions = []
    
    if detected_merchant and len(detected_merchant) > 2:
        regions.append({
            "field": "merchant",
            "label": "Comercio",
            "value": detected_merchant,
            "x": 0.35, "y": 0.15,
            "w": 0.30, "h": 0.10,
            "confidence": 0.3,
            "source": "heuristic",
        })
    
    if detected_discount:
        regions.append({
            "field": "discount",
            "label": "Descuento",
            "value": f"{detected_discount}%",
            "x": 0.65, "y": 0.20,
            "w": 0.25, "h": 0.08,
            "confidence": 0.3,
            "source": "heuristic",
        })
    
    if detected_days:
        regions.append({
            "field": "day",
            "label": "Día",
            "value": ", ".join(detected_days[:3]),
            "x": 0.05, "y": 0.85,
            "w": 0.20, "h": 0.05,
            "confidence": 0.3,
            "source": "heuristic",
        })
    
    if detected_cap:
        regions.append({
            "field": "cap",
            "label": "Tope",
            "value": str(detected_cap),
            "x": 0.55, "y": 0.75,
            "w": 0.35, "h": 0.06,
            "confidence": 0.3,
            "source": "heuristic",
        })
    
    return regions


def find_best_page_for_text(pdf_path: str, detected_text: str) -> Optional[Dict[str, Any]]:
    if not detected_text or len(detected_text) < 10:
        return None
    
    key_fragments = []
    
    if len(detected_text) > 20:
        key_fragments.append(detected_text[:30])
    
    words = detected_text.split()
    for word in words:
        if len(word) > 5:
            key_fragments.append(word)
    
    for fragment in key_fragments:
        result = _find_text_in_pdf(pdf_path, fragment)
        if result:
            return result
    
    return None


def generate_preview_for_item(
    pattern_key: str,
    pdf_path: str,
    page: int = 0,
    detected_text: str = "",
    detected_merchant: str = "",
    detected_discount: Any = None,
    detected_days: List[str] = None,
    detected_cap: Any = None,
) -> Dict[str, Any]:
    item_id = _get_item_id(pattern_key)
    
    result = {
        "image_url": None,
        "crop_url": None,
        "page_number": page,
        "visual_regions": [],
        "page_match_confidence": "high",
    }
    
    page_match = find_best_page_for_text(pdf_path, detected_text)
    
    if page_match:
        result["page_number"] = page_match["page"]
        result["page_match_confidence"] = "high"
        page = page_match["page"]
    
    result["image_url"] = generate_pdf_preview(pdf_path, page, item_id)
    
    if detected_text or detected_merchant:
        regions = extract_visual_regions_from_pdf(
            pdf_path, page, detected_text,
            detected_merchant, detected_discount,
            detected_days or [], detected_cap
        )
        result["visual_regions"] = regions
        
        main_bbox = None
        for reg in regions:
            if reg.get("source") == "pdf_bbox":
                bbox = (
                    reg["x"] * 1000,
                    reg["y"] * 1000,
                    (reg["x"] + reg["w"]) * 1000,
                    (reg["y"] + reg["h"]) * 1000
                )
                if main_bbox is None:
                    main_bbox = bbox
                else:
                    x0 = min(main_bbox[0], bbox[0])
                    y0 = min(main_bbox[1], bbox[1])
                    x1 = max(main_bbox[2], bbox[2])
                    y1 = max(main_bbox[3], bbox[3])
                    main_bbox = (x0, y0, x1, y1)
        
        if main_bbox:
            result["crop_url"] = generate_crop_preview(pdf_path, page, main_bbox, item_id)
    else:
        result["visual_regions"] = _generate_heuristic_regions(
            detected_merchant, detected_discount, detected_days or [], detected_cap
        )
        result["page_match_confidence"] = "low"
    
    return result


def get_preview_status() -> dict:
    previews_dir_exists = PREVIEWS_DIR.exists()
    
    previews = []
    if previews_dir_exists:
        previews = list(PREVIEWS_DIR.glob("*.png"))
    
    crops = []
    if CROPS_DIR.exists():
        crops = list(CROPS_DIR.glob("*.png"))
    
    return {
        "previews_dir_exists": previews_dir_exists,
        "preview_count": len(previews),
        "crop_count": len(crops),
        "sample_files": [p.name for p in previews[:5]],
    }