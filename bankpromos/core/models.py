from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class PromotionModel(BaseModel):
    bank_id: str
    title: str
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    benefit_type: Optional[str] = None
    discount_percent: Optional[Decimal] = None
    installment_count: Optional[int] = None
    valid_days: list[str] = Field(default_factory=list)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source_url: str
    raw_text: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=datetime.now)
    result_quality_score: float = Field(default=0.0)
    result_quality_label: str = Field(default="UNKNOWN")
    merchant_normalized: Optional[str] = None
    category_normalized: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


class FuelPriceModel(BaseModel):
    emblem: str
    fuel_type: str
    price: Decimal
    source_url: str
    updated_at: Optional[datetime] = None
    raw_data: dict = Field(default_factory=dict)

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat() if v else None,
        }