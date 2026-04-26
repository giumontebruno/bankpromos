import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from enum import Enum

from bankpromos.collectors.base import Promotion, Source, SourceType
from bankpromos.pdf_ai_parser import (
    analyze_pdf_with_vision,
    analyze_pdf_url_with_vision,
    get_api_key,
)

logger = logging.getLogger(__name__)

PARSER_MODES = ["classic", "ai", "auto"]


class ParserMode(Enum):
    CLASSIC = "classic"
    AI = "ai"
    AUTO = "auto"


@dataclass
class ParserResult:
    parser_used: str = "classic"
    classic_count: int = 0
    ai_count: int = 0
    final_count: int = 0
    fallback_reason: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def has_api_key() -> bool:
    """Check if OpenAI API key is available."""
    key = get_api_key()
    return key is not None and len(key) > 0


def parse_pdf_with_ai(source: Source, bank_id: str, debug: bool = False) -> List[Dict]:
    """Parse a PDF source using AI vision parser."""
    api_key = get_api_key()
    
    if not api_key:
        logger.warning(f"[PDF-AI] No API key available")
        return []
    
    try:
        if source.url.startswith(("http://", "https://")):
            results = analyze_pdf_url_with_vision(source.url, bank_id)
        else:
            results = analyze_pdf_with_vision(source.url, bank_id)
        
        if debug:
            logger.info(f"[PDF-AI] Extracted {len(results)} promos from {source.url}")
        
        return results
    except Exception as e:
        logger.warning(f"[PDF-AI] Parse error: {e}")
        return []


def ai_result_to_promotion(ai_result: Dict, source: Source) -> Optional[Promotion]:
    """Convert AI result dict to Promotion object."""
    try:
        bank_id = ai_result.get("_bank_id", "unknown")
        
        title = ai_result.get("title", "Promo")
        if not title:
            return None
        
        discount = None
        if ai_result.get("discount_percent"):
            try:
                discount = Decimal(str(ai_result["discount_percent"]))
            except:
                pass
        
        installments = ai_result.get("installment_count")
        if installments:
            try:
                installments = int(installments)
            except:
                installments = None
        
        category = ai_result.get("category", "General")
        
        merchant = ai_result.get("merchant_name")
        
        cap_amount = ai_result.get("cap_amount")
        if cap_amount:
            try:
                cap_amount = Decimal(str(cap_amount))
            except:
                cap_amount = None
        
        valid_days = ai_result.get("valid_days", [])
        if isinstance(valid_days, str):
            valid_days = [valid_days]
        
        valid_from = ai_result.get("valid_from")
        valid_to = ai_result.get("valid_to")
        
        benefit_type = ai_result.get("benefit_type", "reintegro")
        
        payment_method = ai_result.get("payment_method")
        
        conditions = ai_result.get("conditions_text")
        
        promo = Promotion(
            bank_id=bank_id,
            title=title[:100],
            merchant_name=merchant,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount,
            installment_count=installments,
            valid_days=valid_days or [],
            valid_from=valid_from,
            valid_to=valid_to,
            cap_amount=cap_amount,
            payment_method=payment_method,
            source_type=SourceType.PDF,
            source_url=source.url,
            raw_text=conditions,
            metadata={
                "parser": "ai",
                "source_file": ai_result.get("_source_file"),
                "page": ai_result.get("_page"),
            },
        )
        
        return promo
    except Exception as e:
        logger.warning(f"[PDF-AI] Conversion error: {e}")
        return None


def parse_with_fallback(
    classic_promos: List[Promotion],
    source: Source,
    bank_id: str,
    parser_mode: str = "auto",
    debug: bool = False,
) -> ParserResult:
    """Parse PDF with fallback from classic to AI."""
    result = ParserResult(parser_used=parser_mode)
    result.classic_count = len(classic_promos)
    
    if parser_mode == "classic":
        result.final_count = len(classic_promos)
        result.fallback_reason = None
        return result
    
    if parser_mode == "ai":
        if not has_api_key():
            result.errors.append("No AI API key available")
            result.parser_used = "classic"
            result.final_count = len(classic_promos)
            return result
        
        ai_results = parse_pdf_with_ai(source, bank_id, debug)
        result.ai_count = len(ai_results)
        
        ai_promos = []
        for ar in ai_results:
            promo = ai_result_to_promotion(ar, source)
            if promo:
                ai_promos.append(promo)
        
        all_promos = [*classic_promos, *ai_promos]
        result.final_count = len(all_promos)
        return result
    
    if parser_mode == "auto":
        use_ai = False
        
        if result.classic_count == 0:
            use_ai = True
            result.fallback_reason = "no_classic_results"
        elif result.classic_count < 2:
            use_ai = True
            result.fallback_reason = "too_few_results"
        elif result.classic_count < 3 and has_api_key():
            use_ai = True
            result.fallback_reason = "low_result_count"
        
        if not use_ai:
            result.final_count = result.classic_count
            result.parser_used = "classic"
            result.fallback_reason = None
            return result
        
        if not has_api_key():
            result.parser_used = "classic"
            result.final_count = result.classic_count
            result.fallback_reason = "no_ai_key"
            return result
        
        ai_results = parse_pdf_with_ai(source, bank_id, debug)
        result.ai_count = len(ai_results)
        
        if result.ai_count > result.classic_count:
            result.parser_used = "ai"
            result.fallback_reason = result.fallback_reason
        else:
            result.parser_used = "classic"
            result.final_count = result.classic_count
        
        return result
    
    result.final_count = len(classic_promos)
    return result