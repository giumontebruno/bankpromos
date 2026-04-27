import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CORRECTIONS_FILE = DATA_DIR / "extraction_corrections.json"
REVIEW_FILE = DATA_DIR / "review_items.json"

DATA_DIR.mkdir(exist_ok=True)


def _load_corrections() -> List[Dict[str, Any]]:
    if not CORRECTIONS_FILE.exists():
        return []
    try:
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load corrections: {e}")
        return []


def _save_corrections(corrections: List[Dict[str, Any]]) -> None:
    try:
        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save corrections: {e}")
        raise


def _normalize_key(text: str) -> str:
    if not text:
        return ""
    return "".join(c.lower() for c in text if c.isalnum() or c.isspace()).strip()[:200]


def _make_pattern_key(bank_id: str, source_file: str, page: int, detected_text: str) -> str:
    base = f"{bank_id}:{source_file}:{page}:{_normalize_key(detected_text)}"
    return base[:200]


def list_corrections(bank_id: Optional[str] = None, apply_to_future: Optional[bool] = None) -> List[Dict[str, Any]]:
    corrections = _load_corrections()
    if bank_id:
        corrections = [c for c in corrections if c.get("source_bank") == bank_id]
    if apply_to_future is not None:
        corrections = [c for c in corrections if c.get("apply_to_future") == apply_to_future]
    return corrections


def get_correction(id: str) -> Optional[Dict[str, Any]]:
    corrections = _load_corrections()
    for c in corrections:
        if c.get("id") == id:
            return c
    return None


def get_correction_by_key(pattern_key: str) -> Optional[Dict[str, Any]]:
    corrections = _load_corrections()
    for c in corrections:
        if c.get("pattern_key") == pattern_key:
            return c
    return None


def add_correction(
    source_bank: str,
    source_type: str,
    source_file: str,
    source_page: int,
    original_detected_text: str,
    original_detected_merchant: Optional[str] = None,
    corrected_merchant_name: Optional[str] = None,
    corrected_category: Optional[str] = None,
    corrected_discount_percent: Optional[float] = None,
    corrected_installment_count: Optional[int] = None,
    corrected_cap_amount: Optional[float] = None,
    corrected_valid_days: Optional[List[str]] = None,
    corrected_payment_method: Optional[str] = None,
    corrected_conditions_text: Optional[str] = None,
    apply_to_future: bool = True,
    source_crop_path: Optional[str] = None,
) -> Dict[str, Any]:
    corrections = _load_corrections()
    pattern_key = _make_pattern_key(source_bank, source_file, source_page, original_detected_text)

    now = datetime.now().isoformat()
    correction = {
        "id": str(uuid.uuid4()),
        "pattern_key": pattern_key,
        "source_bank": source_bank,
        "source_type": source_type,
        "source_file": source_file,
        "source_page": source_page,
        "source_crop_path": source_crop_path,
        "original_detected_text": original_detected_text,
        "original_detected_merchant": original_detected_merchant,
        "corrected_merchant_name": corrected_merchant_name,
        "corrected_category": corrected_category,
        "corrected_discount_percent": corrected_discount_percent,
        "corrected_installment_count": corrected_installment_count,
        "corrected_cap_amount": corrected_cap_amount,
        "corrected_valid_days": corrected_valid_days or [],
        "corrected_payment_method": corrected_payment_method,
        "corrected_conditions_text": corrected_conditions_text,
        "apply_to_future": apply_to_future,
        "created_at": now,
        "updated_at": now,
    }

    corrections.append(correction)
    _save_corrections(corrections)
    logger.info(f"[CORRECTIONS] Added correction {correction['id']} for {pattern_key}")
    return correction


def update_correction(
    id: str,
    corrected_merchant_name: Optional[str] = None,
    corrected_category: Optional[str] = None,
    corrected_discount_percent: Optional[float] = None,
    corrected_installment_count: Optional[int] = None,
    corrected_cap_amount: Optional[float] = None,
    corrected_valid_days: Optional[List[str]] = None,
    corrected_payment_method: Optional[str] = None,
    corrected_conditions_text: Optional[str] = None,
    apply_to_future: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    corrections = _load_corrections()
    for i, c in enumerate(corrections):
        if c.get("id") == id:
            if corrected_merchant_name is not None:
                c["corrected_merchant_name"] = corrected_merchant_name
            if corrected_category is not None:
                c["corrected_category"] = corrected_category
            if corrected_discount_percent is not None:
                c["corrected_discount_percent"] = corrected_discount_percent
            if corrected_installment_count is not None:
                c["corrected_installment_count"] = corrected_installment_count
            if corrected_cap_amount is not None:
                c["corrected_cap_amount"] = corrected_cap_amount
            if corrected_valid_days is not None:
                c["corrected_valid_days"] = corrected_valid_days
            if corrected_payment_method is not None:
                c["corrected_payment_method"] = corrected_payment_method
            if corrected_conditions_text is not None:
                c["corrected_conditions_text"] = corrected_conditions_text
            if apply_to_future is not None:
                c["apply_to_future"] = apply_to_future
            c["updated_at"] = datetime.now().isoformat()
            corrections[i] = c
            _save_corrections(corrections)
            logger.info(f"[CORRECTIONS] Updated correction {id}")
            return c
    return None


def delete_correction(id: str) -> bool:
    corrections = _load_corrections()
    new_corrections = [c for c in corrections if c.get("id") != id]
    if len(new_corrections) == len(corrections):
        return False
    _save_corrections(new_corrections)
    logger.info(f"[CORRECTIONS] Deleted correction {id}")
    return True


def find_matching_correction(
    bank_id: str,
    detected_text: str,
    detected_merchant: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    corrections = _load_corrections()
    norm_text = _normalize_key(detected_text)
    norm_merchant = _normalize_key(detected_merchant or "")
    norm_bank = bank_id.lower().strip()

    for c in corrections:
        if c.get("source_bank", "").lower().strip() != norm_bank:
            continue

        if c.get("pattern_key"):
            key_text = _normalize_key(c.get("original_detected_text", ""))
            if key_text and norm_text and norm_text in key_text:
                return c
            if key_text == norm_text:
                return c

        if norm_merchant:
            corr_merchant = _normalize_key(c.get("original_detected_merchant", ""))
            if corr_merchant and corr_merchant == norm_merchant:
                return c

    return None


def _load_review_items() -> List[Dict[str, Any]]:
    if not REVIEW_FILE.exists():
        return []
    try:
        with open(REVIEW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load review items: {e}")
        return []


def _save_review_items(items: List[Dict[str, Any]]) -> None:
    try:
        try:
            from bankpromos.preview_service import generate_preview_for_item
        except ImportError:
            generate_preview_for_item = None
        
        for item in items:
            source_file = item.get("source_file", "")
            pattern_key = item.get("pattern_key", "")
            
            if generate_preview_for_item and source_file and source_file.endswith(".pdf") and pattern_key:
                pdf_filename = source_file if "/" not in source_file else source_file.split("/")[-1]
                pdf_path = f"data/pdfs/{pdf_filename}"
                import os
                if os.path.exists(pdf_path):
                    page = item.get("page", 0)
                    image_url = generate_preview_for_item(pattern_key, pdf_path, page)
                    if image_url:
                        item["image_url"] = image_url
        
        existing = _load_review_items()
        
        existing_by_key = {item.get("pattern_key"): item for item in existing if item.get("pattern_key")}
        
        for new_item in items:
            key = new_item.get("pattern_key")
            if key:
                existing_by_key[key] = new_item
        
        merged = list(existing_by_key.values())
        
        with open(REVIEW_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save review items: {e}")


def save_review_items(items: List[Dict[str, Any]]) -> None:
    _save_review_items(items)
    logger.info(f"[CORRECTIONS] Saved {len(items)} review items")


def load_review_items() -> List[Dict[str, Any]]:
    return _load_review_items()


def clear_review_items() -> None:
    _save_review_items([])