import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PATTERNS_FILE = Path("data/visual_patterns.json")


def _load_patterns() -> Dict[str, Any]:
    if PATTERNS_FILE.exists():
        try:
            with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
    return {}


def _save_patterns(patterns: Dict[str, Any]) -> None:
    try:
        PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save patterns: {e}")


def learn_from_correction(correction: Dict[str, Any]) -> None:
    visual_regions = correction.get("visual_regions", [])
    if not visual_regions:
        return
    
    bank = correction.get("source_bank", "")
    category = correction.get("corrected_category", "General")
    
    if not bank:
        return
    
    patterns = _load_patterns()
    
    key = f"{bank}:{category}"
    
    if key not in patterns:
        patterns[key] = {
            "count": 0,
            "fields": {
                "discount": {"x": [], "y": [], "w": [], "h": []},
                "merchant": {"x": [], "y": [], "w": [], "h": []},
                "day": {"x": [], "y": [], "w": [], "h": []},
                "conditions": {"x": [], "y": [], "w": [], "h": []},
                "validity": {"x": [], "y": [], "w": [], "h": []},
                "cap": {"x": [], "y": [], "w": [], "h": []},
            }
        }
    
    for region in visual_regions:
        field = region.get("field")
        if not field or field not in patterns[key]["fields"]:
            continue
        
        region_x = region.get("x", 0)
        region_y = region.get("y", 0)
        region_w = region.get("w", 0)
        region_h = region.get("h", 0)
        
        patterns[key]["fields"][field]["x"].append(region_x)
        patterns[key]["fields"][field]["y"].append(region_y)
        patterns[key]["fields"][field]["w"].append(region_w)
        patterns[key]["fields"][field]["h"].append(region_h)
    
    patterns[key]["count"] += 1
    
    _save_patterns(patterns)
    logger.info(f"Learned pattern for {key} (count: {patterns[key]['count']})")


def get_learned_pattern(bank: str, category: str = "General") -> Optional[Dict[str, Any]]:
    patterns = _load_patterns()
    key = f"{bank}:{category}"
    
    if key not in patterns:
        return None
    
    pattern_data = patterns[key]
    if pattern_data.get("count", 0) < 3:
        return None
    
    fields = pattern_data.get("fields", {})
    result = {"count": pattern_data.get("count", 0), "fields": {}}
    
    for field_name, positions in fields.items():
        xs = positions.get("x", [])
        ys = positions.get("y", [])
        ws = positions.get("w", [])
        hs = positions.get("h", [])
        
        if xs and ys and ws and hs:
            result["fields"][field_name] = {
                "x": sum(xs) / len(xs),
                "y": sum(ys) / len(ys),
                "w": sum(ws) / len(ws),
                "h": sum(hs) / len(hs),
            }
    
    return result if result["fields"] else None


def get_average_position(bank: str, field: str, category: str = "General") -> Optional[Dict[str, float]]:
    pattern = get_learned_pattern(bank, category)
    if not pattern:
        return None
    
    field_data = pattern.get("fields", {}).get(field)
    if not field_data:
        return None
    
    return {
        "x": field_data.get("x", 0),
        "y": field_data.get("y", 0),
        "w": field_data.get("w", 0),
        "h": field_data.get("h", 0),
    }