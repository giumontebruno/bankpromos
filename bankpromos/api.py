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
    benefit_type: Optional[str] = None
    discount_percent: Optional[float] = None
    installment_count: Optional[int] = None
    valid_days: List[str] = Field(default_factory=list)
    source_url: str
    result_quality_score: float = 0.0
    result_quality_label: str = "UNKNOWN"


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
    return {
        "bank_id": promo.bank_id,
        "title": promo.title,
        "merchant_name": promo.merchant_name,
        "category": promo.category,
        "benefit_type": promo.benefit_type,
        "discount_percent": float(promo.discount_percent) if promo.discount_percent else None,
        "installment_count": promo.installment_count,
        "valid_days": promo.valid_days,
        "source_url": promo.source_url,
        "result_quality_score": promo.result_quality_score,
        "result_quality_label": promo.result_quality_label,
    }


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
        raise HTTPException(status_code=500, detail=f"Error collecting data: {str(e)}")


@app.post("/collect-debug")
async def collect_debug(force: bool = False):
    try:
        result = await run_blocking(collect_debug_data, force_refresh=force, db_path=config.db_path)
        return result
    except Exception as e:
        logger.error(f"Collect debug error: {e}")
        raise HTTPException(status_code=500, detail=f"Error collecting debug data: {str(e)}")


@app.post("/collect-fuel")
async def collect_fuel(force: bool = False):
    try:
        prices = get_fuel_data(force_refresh=force, db_path=config.db_path)
        return {
            "count": len(prices),
            "fuel_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Collect fuel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/banks", response_model=List[BankResponse])
async def get_banks():
    banks = list_scrapers()
    bank_names = {
        "py_sudameris": "Sudameris",
        "py_ueno": "Ueno",
        "py_itau": "Itau",
        "py_continental": "Continental",
        "py_bnf": "BNF",
    }
    return [BankResponse(bank_id=b, name=bank_names.get(b, b)) for b in banks]


@app.get("/query", response_model=QueryResponse)
async def query(
    q: str = Query(default="", description="Search query"),
    limit: int = Query(default=10, le=50),
):
    try:
        promos = await run_blocking(get_promotions_data, force_refresh=False, db_path=config.db_path)
        logger.info(f"[QUERY] Loaded {len(promos)} promotions from DB")

        results = query_promotions(promos, q)

        if limit:
            results = results[:limit]

        serialized = [_serialize_promo(p) for p in results]

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bankpromos.api:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
