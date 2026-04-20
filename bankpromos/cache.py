from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bankpromos.storage import get_last_fuel_update, get_last_promotion_update


def is_promotion_cache_fresh(max_age_hours: int = 12, db_path: str = "bankpromos.db") -> bool:
    if not Path(db_path).exists():
        return False

    last_update = get_last_promotion_update(db_path)

    if not last_update:
        return False

    age = datetime.now() - last_update
    return age < timedelta(hours=max_age_hours)


def is_fuel_cache_fresh(max_age_hours: int = 12, db_path: str = "bankpromos.db") -> bool:
    if not Path(db_path).exists():
        return False

    last_update = get_last_fuel_update(db_path)

    if not last_update:
        return False

    age = datetime.now() - last_update
    return age < timedelta(hours=max_age_hours)


def get_last_promotion_update_time(db_path: str = "bankpromos.db") -> Optional[datetime]:
    return get_last_promotion_update(db_path)


def get_last_fuel_update_time(db_path: str = "bankpromos.db") -> Optional[datetime]:
    return get_last_fuel_update(db_path)


def get_cache_age_promotions(db_path: str = "bankpromos.db") -> Optional[timedelta]:
    last_update = get_last_promotion_update(db_path)
    if last_update:
        return datetime.now() - last_update
    return None


def get_cache_age_fuel(db_path: str = "bankpromos.db") -> Optional[timedelta]:
    last_update = get_last_fuel_update(db_path)
    if last_update:
        return datetime.now() - last_update
    return None


def get_cache_status(db_path: str = "bankpromos.db") -> dict:
    promo_age = get_cache_age_promotions(db_path)
    fuel_age = get_cache_age_fuel(db_path)

    return {
        "promotions_fresh": is_promotion_cache_fresh(db_path=db_path),
        "fuel_fresh": is_fuel_cache_fresh(db_path=db_path),
        "promotions_age_hours": promo_age.total_seconds() / 3600 if promo_age else None,
        "fuel_age_hours": fuel_age.total_seconds() / 3600 if fuel_age else None,
        "promotions_updated_at": get_last_promotion_update_time(db_path),
        "fuel_updated_at": get_last_fuel_update_time(db_path),
    }