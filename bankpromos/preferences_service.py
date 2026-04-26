import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES = {
    "favorite_categories": [],
    "hidden_categories": [],
    "favorite_banks": [],
    "prioritize_fuel": False,
    "prioritize_supermarkets": False,
    "prioritize_installments": False,
}

CATEGORY_OPTIONS = [
    "Combustible", "Supermercados", "Gastronomía", "Tecnología",
    "Indumentaria", "Salud", "Viajes", "Hogar", "Belleza",
    "Entretenimiento", "Educación", "Servicios", "General"
]

BANK_OPTIONS = ["py_ueno", "py_itau", "py_continental", "py_sudameris", "py_bnf"]


def _get_preferences_path() -> Path:
    return Path("data/user_preferences.json")


def load_preferences() -> Dict[str, Any]:
    try:
        path = _get_preferences_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load preferences: {e}")
    return dict(DEFAULT_PREFERENCES)


def save_preferences(prefs: Dict[str, Any]) -> bool:
    try:
        path = _get_preferences_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        merged = dict(DEFAULT_PREFERENCES)
        merged.update({
            k: v for k, v in prefs.items() 
            if k in DEFAULT_PREFERENCES
        })
        
        if merged["favorite_categories"]:
            merged["favorite_categories"] = [
                c for c in merged["favorite_categories"] 
                if c in CATEGORY_OPTIONS
            ]
        if merged["hidden_categories"]:
            merged["hidden_categories"] = [
                c for c in merged["hidden_categories"] 
                if c in CATEGORY_OPTIONS
            ]
        if merged["favorite_banks"]:
            merged["favorite_banks"] = [
                b for b in merged["favorite_banks"] 
                if b in BANK_OPTIONS
            ]
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save preferences: {e}")
        return False


def get_preferences() -> Dict[str, Any]:
    return load_preferences()


def update_preferences(
    favorite_categories: Optional[List[str]] = None,
    hidden_categories: Optional[List[str]] = None,
    favorite_banks: Optional[List[str]] = None,
    prioritize_fuel: Optional[bool] = None,
    prioritize_supermarkets: Optional[bool] = None,
    prioritize_installments: Optional[bool] = None,
) -> Dict[str, Any]:
    prefs = load_preferences()
    
    if favorite_categories is not None:
        prefs["favorite_categories"] = favorite_categories
    if hidden_categories is not None:
        prefs["hidden_categories"] = hidden_categories
    if favorite_banks is not None:
        prefs["favorite_banks"] = favorite_banks
    if prioritize_fuel is not None:
        prefs["prioritize_fuel"] = prioritize_fuel
    if prioritize_supermarkets is not None:
        prefs["prioritize_supermarkets"] = prioritize_supermarkets
    if prioritize_installments is not None:
        prefs["prioritize_installments"] = prioritize_installments
    
    save_preferences(prefs)
    return prefs


def reset_preferences() -> Dict[str, Any]:
    save_preferences(DEFAULT_PREFERENCES)
    return dict(DEFAULT_PREFERENCES)


def apply_personalized_boost(
    promos: List[Dict[str, Any]],
    prefs: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if prefs is None:
        prefs = load_preferences()
    
    favorite_cats = prefs.get("favorite_categories", [])
    hidden_cats = prefs.get("hidden_categories", [])
    favorite_banks = prefs.get("favorite_banks", [])
    prioritize_fuel = prefs.get("prioritize_fuel", False)
    prioritize_supermarkets = prefs.get("prioritize_supermarkets", False)
    prioritize_installments = prefs.get("prioritize_installments", False)
    
    result = []
    
    for p in promos:
        category = p.get("category")
        bank_id = p.get("bank_id")
        
        if category in hidden_cats:
            continue
        
        boost = 0
        
        if category in favorite_cats:
            boost += 25
        
        if category == "Combustible" and prioritize_fuel:
            boost += 20
        if category == "Supermercados" and prioritize_supermarkets:
            boost += 20
        
        if bank_id in favorite_banks:
            boost += 15
        
        if prioritize_installments and p.get("installment_count"):
            boost += 10
        
        p_copy = dict(p)
        p_copy["personalized_boost"] = boost
        p_copy["_score"] = p_copy.get("_score", 0) + boost
        
        result.append(p_copy)
    
    result.sort(key=lambda x: -x.get("_score", 0))
    
    return result