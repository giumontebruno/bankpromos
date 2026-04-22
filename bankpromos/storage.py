import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from bankpromos.core.models import FuelPriceModel, PromotionModel

logger = logging.getLogger(__name__)


def _get_connection(db_path: str = "bankpromos.db") -> sqlite3.Connection:
    db_dir = Path(db_path).parent
    if db_dir and not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = "bankpromos.db") -> None:
    db_dir = Path(db_path).parent
    if db_dir and not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id TEXT NOT NULL,
                title TEXT NOT NULL,
                merchant_name TEXT,
                category TEXT,
                benefit_type TEXT,
                discount_percent TEXT,
                installment_count INTEGER,
                valid_days TEXT,
                valid_from TEXT,
                valid_to TEXT,
                source_url TEXT NOT NULL,
                raw_text TEXT,
                raw_data TEXT,
                scraped_at TEXT,
                result_quality_score REAL,
                result_quality_label TEXT,
                merchant_normalized TEXT,
                category_normalized TEXT,
                inserted_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fuel_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emblem TEXT NOT NULL,
                fuel_type TEXT NOT NULL,
                price TEXT NOT NULL,
                source_url TEXT,
                updated_at TEXT,
                raw_data TEXT,
                inserted_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_promotions_bank_id ON promotions(bank_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fuel_prices_emblem ON fuel_prices(emblem)
        """)

        conn.commit()
    finally:
        conn.close()


def _promo_to_row(promo: PromotionModel) -> Dict[str, Any]:
    return {
        "bank_id": promo.bank_id,
        "title": promo.title,
        "merchant_name": promo.merchant_name,
        "category": promo.category,
        "benefit_type": promo.benefit_type,
        "discount_percent": str(promo.discount_percent) if promo.discount_percent else None,
        "installment_count": promo.installment_count,
        "valid_days": json.dumps(promo.valid_days),
        "valid_from": promo.valid_from.isoformat() if promo.valid_from else None,
        "valid_to": promo.valid_to.isoformat() if promo.valid_to else None,
        "source_url": promo.source_url,
        "raw_text": promo.raw_text,
        "raw_data": json.dumps(promo.raw_data),
        "scraped_at": promo.scraped_at.isoformat() if promo.scraped_at else None,
        "result_quality_score": promo.result_quality_score,
        "result_quality_label": promo.result_quality_label,
        "merchant_normalized": promo.merchant_normalized,
        "category_normalized": promo.category_normalized,
    }


def _row_to_promo(row: sqlite3.Row) -> PromotionModel:
    return PromotionModel(
        bank_id=row["bank_id"],
        title=row["title"],
        merchant_name=row["merchant_name"],
        category=row["category"],
        benefit_type=row["benefit_type"],
        discount_percent=Decimal(row["discount_percent"]) if row["discount_percent"] else None,
        installment_count=row["installment_count"],
        valid_days=json.loads(row["valid_days"]) if row["valid_days"] else [],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        source_url=row["source_url"],
        raw_text=row["raw_text"],
        raw_data=json.loads(row["raw_data"]) if row["raw_data"] else {},
        scraped_at=datetime.fromisoformat(row["scraped_at"]) if row["scraped_at"] else None,
        result_quality_score=row["result_quality_score"] or 0.0,
        result_quality_label=row["result_quality_label"] or "UNKNOWN",
        merchant_normalized=row["merchant_normalized"],
        category_normalized=row["category_normalized"],
    )


def _fuel_to_row(fp: FuelPriceModel) -> Dict[str, Any]:
    return {
        "emblem": fp.emblem,
        "fuel_type": fp.fuel_type,
        "price": str(fp.price),
        "source_url": fp.source_url,
        "updated_at": fp.updated_at.isoformat() if fp.updated_at else None,
        "raw_data": json.dumps(fp.raw_data),
    }


def _row_to_fuel(row: sqlite3.Row) -> FuelPriceModel:
    return FuelPriceModel(
        emblem=row["emblem"],
        fuel_type=row["fuel_type"],
        price=Decimal(row["price"]),
        source_url=row["source_url"],
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        raw_data=json.loads(row["raw_data"]) if row["raw_data"] else {},
    )


def save_promotions(promos: List[PromotionModel], db_path: str = "bankpromos.db") -> None:
    if not promos:
        return

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        inserted_at = datetime.now().isoformat()

        for promo in promos:
            row = _promo_to_row(promo)
            row["inserted_at"] = inserted_at

            cursor.execute("""
                INSERT INTO promotions (
                    bank_id, title, merchant_name, category, benefit_type,
                    discount_percent, installment_count, valid_days, valid_from, valid_to,
                    source_url, raw_text, raw_data, scraped_at,
                    result_quality_score, result_quality_label,
                    merchant_normalized, category_normalized, inserted_at
                ) VALUES (
                    :bank_id, :title, :merchant_name, :category, :benefit_type,
                    :discount_percent, :installment_count, :valid_days, :valid_from, :valid_to,
                    :source_url, :raw_text, :raw_data, :scraped_at,
                    :result_quality_score, :result_quality_label,
                    :merchant_normalized, :category_normalized, :inserted_at
                )
            """, row)

        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_promotions_update', :inserted_at, :inserted_at)
        """, {"inserted_at": inserted_at})

        conn.commit()
    finally:
        conn.close()


def load_promotions(db_path: str = "bankpromos.db") -> List[PromotionModel]:
    scraped = _load_scraped_promotions(db_path)
    curated = _load_curated_promotions()
    
    merged = scraped + curated
    merged = _dedupe_promotions(merged)
    merged = _score_promotions(merged)
    
    return merged


def _load_scraped_promotions(db_path: str = "bankpromos.db") -> List[PromotionModel]:
    if not Path(db_path).exists():
        return []

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promotions ORDER BY result_quality_score DESC")
        rows = cursor.fetchall()

        return [_row_to_promo(row) for row in rows]
    finally:
        conn.close()


def _load_curated_promotions() -> List[PromotionModel]:
    base_dir = Path(__file__).parent.parent / "data"
    curated_path = base_dir / "curated_promotions.json"
    if not curated_path.exists():
        logger.warning(f"[CURATED] File not found: {curated_path}")
        return []
    
    try:
        with open(curated_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.warning(f"[CURATED] Failed to load curated data")
        return []
    
    promos = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            promo = PromotionModel(
                bank_id=item.get("bank_id", ""),
                title=item.get("title", ""),
                merchant_name=item.get("merchant_name"),
                category=item.get("category"),
                benefit_type=item.get("benefit_type"),
                discount_percent=Decimal(str(item.get("discount_percent", 0))) if item.get("discount_percent") else None,
                installment_count=item.get("installment_count"),
                valid_days=item.get("valid_days", []),
                source_url=item.get("source_url", ""),
                raw_text=item.get("raw_text"),
                raw_data={"curated": True},
                result_quality_score=1.0,
                result_quality_label="CURATED",
            )
            promos.append(promo)
        except Exception:
            continue
    
    return promos


def _dedupe_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    if not promos:
        return []
    
    seen = set()
    unique = []
    for p in promos:
        key = f"{p.bank_id}:{(p.merchant_name or p.title or '').lower()}:{p.discount_percent or ''}"
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    return unique


def _score_promotions(promos: List[PromotionModel]) -> List[PromotionModel]:
    scored = []
    for p in promos:
        score = 0.0
        
        if p.result_quality_label == "CURATED":
            score = 1.0
        elif p.result_quality_label == "actionable":
            score = 0.8
        elif p.merchant_name:
            score = 0.5
        
        if p.discount_percent:
            pct = float(p.discount_percent)
            if pct >= 20:
                score += 0.3
            elif pct >= 15:
                score += 0.2
            elif pct >= 10:
                score += 0.1
        
        if p.valid_days:
            score += 0.1
        
        p.result_quality_score = score
        scored.append(p)
    
    return sorted(scored, key=lambda x: x.result_quality_score, reverse=True)


def clear_promotions(db_path: str = "bankpromos.db") -> None:
    if not Path(db_path).exists():
        return

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM promotions")
        cursor.execute("DELETE FROM metadata WHERE key = 'last_promotions_update'")
        conn.commit()
    finally:
        conn.close()


def save_fuel_prices(prices: List[FuelPriceModel], db_path: str = "bankpromos.db") -> None:
    if not prices:
        return

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        inserted_at = datetime.now().isoformat()

        cursor.execute("DELETE FROM fuel_prices")

        for fp in prices:
            row = _fuel_to_row(fp)
            row["inserted_at"] = inserted_at

            cursor.execute("""
                INSERT INTO fuel_prices (
                    emblem, fuel_type, price, source_url, updated_at, raw_data, inserted_at
                ) VALUES (
                    :emblem, :fuel_type, :price, :source_url, :updated_at, :raw_data, :inserted_at
                )
            """, row)

        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_fuel_update', :inserted_at, :inserted_at)
        """, {"inserted_at": inserted_at})

        conn.commit()
    finally:
        conn.close()


def load_fuel_prices(db_path: str = "bankpromos.db") -> List[FuelPriceModel]:
    if not Path(db_path).exists():
        return []

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fuel_prices")
        rows = cursor.fetchall()

        return [_row_to_fuel(row) for row in rows]
    finally:
        conn.close()


def clear_fuel_prices(db_path: str = "bankpromos.db") -> None:
    if not Path(db_path).exists():
        return

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM fuel_prices")
        cursor.execute("DELETE FROM metadata WHERE key = 'last_fuel_update'")
        conn.commit()
    finally:
        conn.close()


def get_last_promotion_update(db_path: str = "bankpromos.db") -> Optional[datetime]:
    if not Path(db_path).exists():
        return None

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT value FROM metadata WHERE key = 'last_promotions_update'
        """)
        row = cursor.fetchone()

        if row:
            return datetime.fromisoformat(row[0])
        return None
    finally:
        conn.close()


def get_last_fuel_update(db_path: str = "bankpromos.db") -> Optional[datetime]:
    if not Path(db_path).exists():
        return None

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT value FROM metadata WHERE key = 'last_fuel_update'
        """)
        row = cursor.fetchone()

        if row:
            return datetime.fromisoformat(row[0])
        return None
    finally:
        conn.close()