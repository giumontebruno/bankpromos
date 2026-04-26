from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

import logging

logger = logging.getLogger(__name__)


class UnifiedPromotion(BaseModel):
    bank_id: str
    title: str

    merchant_name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None

    benefit_type: Optional[str] = None
    discount_percent: Optional[Decimal] = None
    extra_discount_percent: Optional[Decimal] = None
    installments: Optional[int] = None
    installment_type: Optional[str] = None

    cap_amount: Optional[Decimal] = None
    cap_percent: Optional[Decimal] = None
    min_purchase: Optional[Decimal] = None

    payment_method: Optional[str] = None
    card_type: Optional[str] = None
    merchant_group: Optional[str] = None
    emblem: Optional[str] = None

    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    valid_days: List[str] = Field(default_factory=list)

    source_type: str = "unknown"
    source_url: str = ""
    pdf_url: Optional[str] = None
    raw_text: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    scraped_at: datetime = Field(default_factory=datetime.now)

    collection_method: str = "collector"
    extraction_confidence: float = 0.0

    is_active: bool = True

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_legacy(cls, legacy_promo) -> "UnifiedPromotion":
        """Convert from existing PromotionModel."""
        return cls(
            bank_id=legacy_promo.bank_id,
            title=legacy_promo.title,
            merchant_name=legacy_promo.merchant_name,
            category=legacy_promo.category,
            benefit_type=legacy_promo.benefit_type,
            discount_percent=legacy_promo.discount_percent,
            installments=legacy_promo.installment_count,
            cap_amount=legacy_promo.cap_amount,
            payment_method=legacy_promo.payment_method,
            emblem=legacy_promo.emblem,
            valid_from=legacy_promo.valid_from,
            valid_to=legacy_promo.valid_to,
            valid_days=legacy_promo.valid_days or [],
            source_type="legacy",
            source_url=legacy_promo.source_url or "",
            raw_text=legacy_promo.raw_text,
            raw_data=legacy_promo.raw_data or {},
            scraped_at=legacy_promo.scraped_at,
        )

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to dict compatible with existing storage."""
        return {
            "bank_id": self.bank_id,
            "title": self.title,
            "merchant_name": self.merchant_name,
            "category": self.category,
            "benefit_type": self.benefit_type,
            "discount_percent": str(self.discount_percent) if self.discount_percent else None,
            "installment_count": self.installments,
            "valid_days": self.valid_days,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "source_url": self.source_url,
            "raw_text": self.raw_text,
            "raw_data": self.raw_data,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "result_quality_score": self.extraction_confidence,
            "result_quality_label": "COLLECTOR",
        }


def convert_to_legacy(promos: List[UnifiedPromotion]) -> List[Dict[str, Any]]:
    """Convert unified promotions to legacy storage format."""
    return [p.to_legacy_dict() for p in promos]