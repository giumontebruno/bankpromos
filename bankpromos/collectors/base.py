from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceType(Enum):
    PDF = "pdf"
    HTML = "html"
    API = "api"
    UNKNOWN = "unknown"


@dataclass
class Source:
    source_type: SourceType
    url: str
    title: Optional[str] = None
    discovered_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectorResult:
    bank_id: str
    sources_discovered: List[Source] = field(default_factory=list)
    sources_parsed: int = 0
    promotions_found: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseCollector(ABC):
    bank_id: str = "unknown"
    display_name: str = "Unknown Bank"

    @abstractmethod
    def discover_sources(self) -> List[Source]:
        """Discover available sources for this collector."""
        pass

    @abstractmethod
    def collect(self, sources: Optional[List[Source]] = None) -> List["Promotion"]:
        """Collect promotions from sources."""
        pass

    def get_display_name(self) -> str:
        return self.display_name


@dataclass
class Promotion:
    bank_id: str
    title: str
    merchant_name: Optional[str] = None
    category: Optional[str] = None

    benefit_type: Optional[str] = None
    discount_percent: Optional[Decimal] = None
    installment_count: Optional[int] = None
    installment_type: Optional[str] = None

    valid_days: List[str] = field(default_factory=list)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    cap_amount: Optional[Decimal] = None
    cap_percent: Optional[Decimal] = None

    payment_method: Optional[str] = None
    card_type: Optional[str] = None
    emblem: Optional[str] = None

    source_type: SourceType = SourceType.UNKNOWN
    source_url: str = ""
    raw_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    needs_review: bool = False
    review_reason: Optional[str] = None
    pattern_key: Optional[str] = None

    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bank_id": self.bank_id,
            "title": self.title,
            "merchant_name": self.merchant_name,
            "category": self.category,
            "benefit_type": self.benefit_type,
            "discount_percent": str(self.discount_percent) if self.discount_percent else None,
            "installment_count": self.installment_count,
            "installment_type": self.installment_type,
            "valid_days": self.valid_days,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "cap_amount": str(self.cap_amount) if self.cap_amount else None,
            "cap_percent": str(self.cap_percent) if self.cap_percent else None,
            "payment_method": self.payment_method,
            "card_type": self.card_type,
            "emblem": self.emblem,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "raw_text": self.raw_text,
            "metadata": self.metadata,
            "needs_review": self.needs_review,
            "review_reason": self.review_reason,
            "pattern_key": self.pattern_key,
        }