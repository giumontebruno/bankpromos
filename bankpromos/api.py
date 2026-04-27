import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bankpromos import list_scrapers
from bankpromos.cache import get_cache_status
from bankpromos.config import config
from bankpromos.data_service import (
    collect_all_data,
    collect_debug_data,
    get_fuel_data,
    get_promotions_data,
)
from bankpromos.fuel_prices import get_fuel_prices
from bankpromos.fuel_query import find_best_fuel_promotions
from bankpromos.query_engine import query_promotions
from bankpromos.storage import init_db, load_promotions, load_fuel_prices, get_last_promotion_update, get_last_fuel_update
from bankpromos.ui_output import to_ui_promo, group_promos_by_category, group_promos_by_bank, filter_public_promos

logging.basicConfig(level=logging.INFO if not config.debug else logging.DEBUG)
logger = logging.getLogger(__name__)

port = int(os.getenv("PORT", "8000"))

_thread_pool = ThreadPoolExecutor(max_workers=4)

T = TypeVar("T")


async def run_blocking(func: Callable[..., T], *args, **kwargs) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _thread_pool,
        partial(func, *args, **kwargs)
    )


app = FastAPI(
    title="Bank Promos PY API",
    description="API para consultas de promociones y beneficios bancarios en Paraguay",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str


class CacheStatusResponse(BaseModel):
    promotions_fresh: bool = False
    fuel_fresh: bool = False
    promotions_age_hours: Optional[float] = None
    fuel_age_hours: Optional[float] = None
    promotions_updated_at: Optional[str] = None
    fuel_updated_at: Optional[str] = None


class CollectResponse(BaseModel):
    promotions_count: int = 0
    fuel_prices_count: int = 0
    promos_updated: Optional[str] = None
    fuel_updated: Optional[str] = None


class DataStatusResponse(BaseModel):
    db_path: str
    file_exists: bool
    file_size_bytes: int
    promotions_count: int
    fuel_count: int
    latest_promotion_inserted_at: Optional[str] = None
    latest_fuel_inserted_at: Optional[str] = None
    disable_live_scraping: bool
    curated_count: int = 0
    scraped_count: int = 0


class BankResponse(BaseModel):
    bank_id: str
    name: str


class PromotionResult(BaseModel):
    bank_id: str
    title: str
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    is_category_level: bool = False
    promo_type_display: str = "local"
    display_name: str = ""
    display_title: str = ""
    display_subtitle: Optional[str] = None
    benefit_type: Optional[str] = None
    discount_percent: Optional[float] = None
    installment_count: Optional[int] = None
    cap_amount: Optional[float] = None
    cap_display: Optional[str] = None
    valid_days: List[str] = Field(default_factory=list)
    valid_days_display: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    conditions_short: Optional[str] = None
    highlight_value: str = ""
    highlight_type: str = ""
    emblem: Optional[str] = None
    source_url: str = ""
    quality_score: float = 0.0
    quality_label: Optional[str] = None
    result_quality_score: float = 0.0
    result_quality_label: Optional[str] = None


class FuelResultEntry(BaseModel):
    bank_id: str
    emblem: str
    fuel_type: str
    base_price: float
    discount_percent: Optional[float] = None
    estimated_final_price: float
    savings: float
    valid_days: List[str] = Field(default_factory=list)
    source_url: str
    quality_score: float = 0.0
    promo_title: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    total_results: int = 0
    results: List[PromotionResult] = Field(default_factory=list)


class FuelQueryResponse(BaseModel):
    query: str
    fuel_type: str
    total_results: int = 0
    results: List[FuelResultEntry] = Field(default_factory=list)


def _serialize_promo(promo) -> Dict[str, Any]:
    promo_dict = promo if isinstance(promo, dict) else {
        "bank_id": promo.bank_id,
        "title": promo.title,
        "merchant_name": promo.merchant_name,
        "category": promo.category,
        "benefit_type": promo.benefit_type,
        "discount_percent": float(promo.discount_percent) if promo.discount_percent else None,
        "installment_count": promo.installment_count,
        "valid_days": promo.valid_days,
        "cap_amount": str(promo.cap_amount) if promo.cap_amount else None,
        "valid_from": promo.valid_from.isoformat() if promo.valid_from else None,
        "valid_to": promo.valid_to.isoformat() if promo.valid_to else None,
        "conditions_text": promo.conditions_text,
        "payment_method": promo.payment_method,
        "emblem": promo.emblem,
        "source_url": promo.source_url,
        "raw_text": promo.raw_text,
        "result_quality_score": promo.result_quality_score,
        "result_quality_label": promo.result_quality_label,
    }
    return to_ui_promo(promo_dict)


@app.on_event("startup")
async def startup_event():
    logger.info(f"[STARTUP] Starting Bank Promos PY API on port {port}...")

    db_info = config.validate_db_exists()
    logger.info(f"[STARTUP] DB PATH: {db_info['db_path']}")
    logger.info(f"[STARTUP] EXISTS: {db_info['exists']}")
    logger.info(f"[STARTUP] SIZE: {db_info['size_bytes']} bytes")

    try:
        config.ensure_db_dir()
        init_db(config.db_path)
    except Exception as e:
        logger.error(f"[STARTUP] Failed to initialize database: {e}")

    try:
        promos = load_promotions(config.db_path)
        fuel = load_fuel_prices(config.db_path)
        scraped = [p for p in promos if p.result_quality_label != "CURATED"]
        curated = [p for p in promos if p.result_quality_label == "CURATED"]
        logger.info(f"[STARTUP] PROMOS: {len(promos)} (scraped={len(scraped)}, curated={len(curated)})")
        logger.info(f"[STARTUP] FUEL: {len(fuel)}")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not load data: {e}")

    logger.info(f"[STARTUP] DISABLE_LIVE_SCRAPING: {config.disable_live_scraping}")
    logger.info(f"[STARTUP] Startup complete")


@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="ok")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@app.get("/cache", response_model=CacheStatusResponse)
async def get_cache():
    try:
        status = get_cache_status(config.db_path)
        promo_dt = status.get("promotions_updated_at")
        fuel_dt = status.get("fuel_updated_at")
        return CacheStatusResponse(
            promotions_fresh=status.get("promotions_fresh", False),
            fuel_fresh=status.get("fuel_fresh", False),
            promotions_age_hours=status.get("promotions_age_hours"),
            fuel_age_hours=status.get("fuel_age_hours"),
            promotions_updated_at=promo_dt.isoformat() if promo_dt else None,
            fuel_updated_at=fuel_dt.isoformat() if fuel_dt else None,
        )
    except Exception as e:
        logger.error(f"Cache status error: {e}")
        return CacheStatusResponse(promotions_fresh=False, fuel_fresh=False)


@app.get("/data-status", response_model=DataStatusResponse)
async def data_status():
    try:
        db_info = config.validate_db_exists()
        promos = load_promotions(config.db_path)
        fuel = load_fuel_prices(config.db_path)
        promo_dt = get_last_promotion_update(config.db_path)
        fuel_dt = get_last_fuel_update(config.db_path)
        
        scraped = [p for p in promos if p.result_quality_label != "CURATED"]
        curated = [p for p in promos if p.result_quality_label == "CURATED"]

        return DataStatusResponse(
            db_path=db_info["db_path"],
            file_exists=db_info["exists"],
            file_size_bytes=db_info["size_bytes"],
            promotions_count=len(promos),
            fuel_count=len(fuel),
            latest_promotion_inserted_at=promo_dt.isoformat() if promo_dt else None,
            latest_fuel_inserted_at=fuel_dt.isoformat() if fuel_dt else None,
            disable_live_scraping=config.disable_live_scraping,
            curated_count=len(curated),
            scraped_count=len(scraped),
        )
    except Exception as e:
        logger.error(f"Data status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/collect", response_model=CollectResponse)
async def collect_data(force: bool = False):
    try:
        result = await run_blocking(collect_all_data, force_refresh=force, db_path=config.db_path)
        return CollectResponse(
            promotions_count=result["promotions_count"],
            fuel_prices_count=result["fuel_prices_count"],
            promos_updated=result.get("promos_updated"),
            fuel_updated=result.get("fuel_updated"),
        )
    except Exception as e:
        logger.error(f"Collect error: {e}")
        raise HTTPException(status_code=500, detail=f"Collect error: {str(e)}")


@app.get("/today", response_model=QueryResponse)
async def today(
    category: str = Query(default="", description="Filter by category"),
    limit: int = Query(default=20, le=50),
    group_by: str = Query(default="", description="Group by: category, bank"),
):
    try:
        from bankpromos.core.normalizer import get_best_promotions_today
        from bankpromos.ranking_service import filter_noise, rank_promos_for_today, diversify_promos

        promos = await run_blocking(get_promotions_data, force_refresh=False, db_path=config.db_path)
        
        if category:
            results = get_best_promotions_today(promos, category=category or None, limit=limit * 3, include_week=True)
        else:
            results = get_best_promotions_today(promos, category=None, limit=limit * 3, include_week=True)
        
        serialized = [_serialize_promo(p) for p in results]
        serialized = [s for s in serialized if s is not None]
        serialized = filter_noise(serialized)
        serialized = filter_public_promos(serialized)
        
        if not category:
            serialized = diversify_promos(serialized, max_per_category=3, min_categories=3)
            serialized = rank_promos_for_today(serialized, limit=limit)
        else:
            serialized = rank_promos_for_today(serialized, limit=limit)

        try:
            from bankpromos.analytics_service import track_event
            track_event("today_view", category=category or None)
        except Exception:
            pass

        if group_by == "category":
            groups = group_promos_by_category(serialized)
            return {"query": f"today{(':' + category) if category else ''}", "total_results": len(serialized), "results": serialized, "groups": groups}
        if group_by == "bank":
            groups = group_promos_by_bank(serialized)
            return {"query": f"today{(':' + category) if category else ''}", "total_results": len(serialized), "results": serialized, "groups": groups}

        return QueryResponse(
            query=f"today{(':' + category) if category else ''}",
            total_results=len(serialized),
            results=serialized,
        )
    except Exception as e:
        logger.error(f"Today error: {e}")
        raise HTTPException(status_code=500, detail=f"Today error: {str(e)}")


@app.get("/today/personalized", response_model=QueryResponse)
async def today_personalized(
    limit: int = Query(default=20, le=50),
):
    try:
        from bankpromos.core.normalizer import get_best_promotions_today
        from bankpromos.ranking_service import filter_noise, rank_promos_for_today
        from bankpromos.preferences_service import load_preferences, apply_personalized_boost

        promos = await run_blocking(get_promotions_data, force_refresh=False, db_path=config.db_path)
        results = get_best_promotions_today(promos, category=None, limit=limit * 3)
        
        serialized = [_serialize_promo(p) for p in results]
        serialized = filter_noise(serialized)
        serialized = rank_promos_for_today(serialized, limit=limit * 3)
        
        prefs = load_preferences()
        serialized = apply_personalized_boost(serialized, prefs)

        try:
            from bankpromos.analytics_service import track_event
            track_event("today_personalized_view")
        except Exception:
            pass

        return QueryResponse(
            query="today:personalized",
            total_results=len(serialized),
            results=serialized[:limit],
        )
    except Exception as e:
        logger.error(f"Today personalized error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/preferences")
async def get_preferences():
    try:
        from bankpromos.preferences_service import get_preferences
        return get_preferences()
    except Exception as e:
        logger.error(f"Preferences error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/preferences")
async def update_preferences(prefs: dict):
    try:
        from bankpromos.preferences_service import update_preferences
        updated = update_preferences(
            favorite_categories=prefs.get("favorite_categories"),
            hidden_categories=prefs.get("hidden_categories"),
            favorite_banks=prefs.get("favorite_banks"),
            prioritize_fuel=prefs.get("prioritize_fuel"),
            prioritize_supermarkets=prefs.get("prioritize_supermarkets"),
            prioritize_installments=prefs.get("prioritize_installments"),
        )

        try:
            from bankpromos.analytics_service import track_event
            track_event("preference_save", metadata={"fav_cats": len(prefs.get("favorite_categories", []))})
        except Exception:
            pass

        return updated
    except Exception as e:
        logger.error(f"Preferences update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/preferences/reset")
async def reset_preferences():
    try:
        from bankpromos.preferences_service import reset_preferences
        return reset_preferences()
    except Exception as e:
        logger.error(f"Preferences reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/summary")
async def analytics_summary():
    try:
        from bankpromos.analytics_service import get_today_summary, get_analytics_summary
        return {
            "today": get_today_summary(),
            "overall": get_analytics_summary(),
        }
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/top-queries")
async def analytics_top_queries(limit: int = Query(default=10, le=20)):
    try:
        from bankpromos.analytics_service import get_top_queries
        return {"results": get_top_queries(limit=limit)}
    except Exception as e:
        logger.error(f"Analytics top queries error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/top-categories")
async def analytics_top_categories(limit: int = Query(default=10, le=20)):
    try:
        from bankpromos.analytics_service import get_top_categories
        return {"results": get_top_categories(limit=limit)}
    except Exception as e:
        logger.error(f"Analytics top categories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query", response_model=QueryResponse)
async def query(
    q: str = Query(default="", description="Search query"),
    limit: int = Query(default=10, le=50),
    group_by: str = Query(default="", description="Group by: category, bank"),
):
    try:
        promos = await run_blocking(get_promotions_data, force_refresh=False, db_path=config.db_path)
        logger.info(f"[QUERY] Loaded {len(promos)} promotions from DB")

        results = query_promotions(promos, q)

        if limit:
            results = results[:limit]

        serialized = [_serialize_promo(p) for p in results]
        serialized = [s for s in serialized if s is not None]
        
        from bankpromos.ranking_service import filter_noise, rank_promos_for_today
        serialized = filter_noise(serialized)
        serialized = filter_public_promos(serialized)
        serialized = rank_promos_for_today(serialized, limit=limit)

        try:
            from bankpromos.analytics_service import track_event
            track_event("search_query", query=q)
        except Exception:
            pass

        if group_by == "category":
            groups = group_promos_by_category(serialized)
            return {"query": q, "total_results": len(serialized), "results": serialized, "groups": groups}
        if group_by == "bank":
            groups = group_promos_by_bank(serialized)
            return {"query": q, "total_results": len(serialized), "results": serialized, "groups": groups}

        return QueryResponse(
            query=q,
            total_results=len(serialized),
            results=serialized,
        )
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.get("/fuel", response_model=FuelQueryResponse)
async def fuel_query(
    q: str = Query(default="", description="Fuel query"),
    limit: int = Query(default=10, le=50),
):
    try:
        from bankpromos.fuel_prices import normalize_fuel_type, normalize_emblem
        from bankpromos.fuel_query import find_best_fuel_promotions

        promos = await run_blocking(get_promotions_data, force_refresh=False, db_path=config.db_path)
        fuel_prices = get_fuel_data(force_refresh=False, db_path=config.db_path)

        fuel_type = normalize_fuel_type(q) or "nafta_95"
        emblem = normalize_emblem(q)

        matches = find_best_fuel_promotions(promos, fuel_prices, fuel_type, emblem)

        if limit:
            matches = matches[:limit]

        results = []
        for m in matches:
            results.append(
                FuelResultEntry(
                    bank_id=m["bank_id"],
                    emblem=m["emblem"],
                    fuel_type=m["fuel_type"],
                    base_price=float(m["base_price"]),
                    discount_percent=float(m["discount_percent"]) if m["discount_percent"] else None,
                    estimated_final_price=float(m["estimated_final_price"]),
                    savings=float(m["savings"]),
                    valid_days=m["valid_days"],
                    source_url=m["source_url"],
                    quality_score=m["quality_score"],
                    promo_title=m.get("promo_title"),
                )
            )

        try:
            from bankpromos.analytics_service import track_event
            track_event("fuel_query", query=q)
        except Exception:
            pass

        return FuelQueryResponse(
            query=q,
            fuel_type=fuel_type,
            total_results=len(results),
            results=results,
        )
    except Exception as e:
        logger.error(f"Fuel query error: {e}")
        raise HTTPException(status_code=500, detail=f"Fuel query error: {str(e)}")


@app.get("/fuel-prices")
async def get_fuel_prices_api():
    try:
        prices = get_fuel_data(force_refresh=False, db_path=config.db_path)
        return {
            "count": len(prices),
            "prices": [
                {
                    "emblem": p.emblem,
                    "fuel_type": p.fuel_type,
                    "price": float(p.price),
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in prices
            ],
        }
    except Exception as e:
        logger.error(f"Fuel prices error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/curated")
async def list_curated():
    try:
        from bankpromos.curated_service import list_curated_promotions, ensure_curated_ids
        ensure_curated_ids()
        promos = list_curated_promotions()
        return {"total": len(promos), "results": promos}
    except Exception as e:
        logger.error(f"Admin curated list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/curated")
async def create_curated(promo: dict):
    try:
        from bankpromos.curated_service import add_curated_promotion
        item_id = add_curated_promotion(promo)
        if item_id:
            return {"id": item_id, "success": True}
        raise HTTPException(status_code=400, detail="Failed to add curated")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Admin curated create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/curated/{item_id}")
async def update_curated(item_id: str, updates: dict):
    try:
        from bankpromos.curated_service import update_curated_promotion
        success = update_curated_promotion(item_id, updates)
        if success:
            return {"id": item_id, "success": True}
        raise HTTPException(status_code=404, detail="Curated promo not found")
    except Exception as e:
        logger.error(f"Admin curated update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/curated/{item_id}")
async def delete_curated(item_id: str):
    try:
        from bankpromos.curated_service import delete_curated_promotion
        success = delete_curated_promotion(item_id)
        if success:
            return {"id": item_id, "success": True}
        raise HTTPException(status_code=404, detail="Curated promo not found")
    except Exception as e:
        logger.error(f"Admin curated update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/corrections")
async def list_corrections(bank_id: str = Query(default=""), apply_to_future: bool = Query(default=None)):
    try:
        from bankpromos.corrections_service import list_corrections as _list_corrections
        result = _list_corrections(
            bank_id=bank_id or None,
            apply_to_future=apply_to_future if apply_to_future is not None else None,
        )
        return {"total": len(result), "results": result}
    except Exception as e:
        logger.error(f"Admin corrections list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/corrections")
async def create_correction(correction: dict):
    try:
        from bankpromos.corrections_service import add_correction
        result = add_correction(
            source_bank=correction.get("source_bank", ""),
            source_type=correction.get("source_type", "pdf"),
            source_file=correction.get("source_file", ""),
            source_page=correction.get("source_page", 0),
            original_detected_text=correction.get("original_detected_text", ""),
            original_detected_merchant=correction.get("original_detected_merchant"),
            corrected_merchant_name=correction.get("corrected_merchant_name"),
            corrected_category=correction.get("corrected_category"),
            corrected_discount_percent=correction.get("corrected_discount_percent"),
            corrected_installment_count=correction.get("corrected_installment_count"),
            corrected_cap_amount=correction.get("corrected_cap_amount"),
            corrected_valid_days=correction.get("corrected_valid_days"),
            corrected_payment_method=correction.get("corrected_payment_method"),
            corrected_conditions_text=correction.get("corrected_conditions_text"),
            apply_to_future=correction.get("apply_to_future", True),
            source_crop_path=correction.get("source_crop_path"),
        )
        return {"id": result["id"], "success": True}
    except Exception as e:
        logger.error(f"Admin correction create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/corrections/{correction_id}")
async def update_correction(correction_id: str, updates: dict):
    try:
        from bankpromos.corrections_service import update_correction
        result = update_correction(
            id=correction_id,
            corrected_merchant_name=updates.get("corrected_merchant_name"),
            corrected_category=updates.get("corrected_category"),
            corrected_discount_percent=updates.get("corrected_discount_percent"),
            corrected_installment_count=updates.get("corrected_installment_count"),
            corrected_cap_amount=updates.get("corrected_cap_amount"),
            corrected_valid_days=updates.get("corrected_valid_days"),
            corrected_payment_method=updates.get("corrected_payment_method"),
            corrected_conditions_text=updates.get("corrected_conditions_text"),
            apply_to_future=updates.get("apply_to_future"),
        )
        if result:
            return {"id": correction_id, "success": True}
        raise HTTPException(status_code=404, detail="Correction not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin correction update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/corrections/{correction_id}")
async def delete_correction(correction_id: str):
    try:
        from bankpromos.corrections_service import delete_correction
        success = delete_correction(correction_id)
        if success:
            return {"id": correction_id, "success": True}
        raise HTTPException(status_code=404, detail="Correction not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin correction delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/review-items")
async def get_review_items():
    try:
        from bankpromos.corrections_service import load_review_items
        items = load_review_items()
        return {"total": len(items), "results": items}
    except Exception as e:
        logger.error(f"Admin review items error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary")
async def get_summary():
    try:
        from bankpromos.summary_service import generate_summary, load_summary
        summary = generate_summary("data/bankpromos.db")
        return summary
    except Exception as e:
        logger.error(f"Summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/changes")
async def get_changes():
    try:
        from bankpromos.summary_service import load_summary
        prev = load_summary()
        if not prev:
            return {"message": "No previous summary available"}
        from bankpromos.summary_service import generate_summary
        current = generate_summary("data/bankpromos.db")
        prev_total = prev.get("total_promos", 0)
        return {
            "new_promos": max(0, current.total_promos - prev_total),
            "removed_promos": max(0, prev_total - current.total_promos),
            "previous_total": prev_total,
            "current_total": current.total_promos,
        }
    except Exception as e:
        logger.error(f"Changes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bankpromos.api:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
