import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from bankpromos.core.models import PromotionModel

logger = logging.getLogger(__name__)

CURATED_FILE = Path("data/curated_promotions.json")


class CuratedService:
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or CURATED_FILE

    def load_all(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_all(self, promos: List[Dict[str, Any]]) -> bool:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(promos, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save curated: {e}")
            return False

    def list_all(self) -> List[Dict[str, Any]]:
        return self.load_all()

    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        for item in self.load_all():
            if item.get("id") == item_id:
                return item
        return None

    def add(self, promo: Dict[str, Any]) -> Optional[str]:
        promos = self.load_all()

        promo["id"] = str(uuid.uuid4())[:8]
        promo["curated"] = True
        promo["created_at"] = datetime.now().isoformat()

        promos.append(promo)

        if self.save_all(promos):
            return promo["id"]
        return None

    def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        promos = self.load_all()

        for i, item in enumerate(promos):
            if item.get("id") == item_id:
                updates["updated_at"] = datetime.now().isoformat()
                promos[i] = {**item, **updates}
                return self.save_all(promos)

        return False

    def delete(self, item_id: str) -> bool:
        promos = self.load_all()

        new_promos = [p for p in promos if p.get("id") != item_id]

        if len(new_promos) < len(promos):
            return self.save_all(new_promos)

        return False

    def validate(self, promo: Dict[str, Any]) -> Dict[str, Any]:
        errors = []

        if not promo.get("bank_id"):
            errors.append("bank_id is required")
        if not promo.get("merchant_name"):
            errors.append("merchant_name is required")
        if not promo.get("title"):
            errors.append("title is required")

        discount = promo.get("discount_percent")
        if discount:
            try:
                int(discount)
            except:
                errors.append("discount_percent must be numeric")

        return {"valid": len(errors) == 0, "errors": errors}


def list_curated_promotions() -> List[Dict[str, Any]]:
    service = CuratedService()
    return service.list_all()


def get_curated_promotion(item_id: str) -> Optional[Dict[str, Any]]:
    service = CuratedService()
    return service.get_by_id(item_id)


def add_curated_promotion(promo: Dict[str, Any]) -> Optional[str]:
    service = CuratedService()
    validation = service.validate(promo)
    if not validation["valid"]:
        raise ValueError(", ".join(validation["errors"]))
    return service.add(promo)


def update_curated_promotion(item_id: str, updates: Dict[str, Any]) -> bool:
    service = CuratedService()
    return service.update(item_id, updates)


def delete_curated_promotion(item_id: str) -> bool:
    service = CuratedService()
    return service.delete(item_id)


def ensure_curated_ids() -> None:
    """Ensure all curated promos have IDs."""
    service = CuratedService()
    promos = service.load_all()
    changed = False

    for promo in promos:
        if "id" not in promo:
            promo["id"] = str(uuid.uuid4())[:8]
            changed = True

    if changed:
        service.save_all(promos)
        logger.info(f"Added IDs to {sum(1 for p in promos if 'id' in p)} curated promos")