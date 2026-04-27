import logging
import os
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from bankpromos.collectors.base import BaseCollector, Promotion, Source, SourceType, CollectorResult
from bankpromos.pdf_parser import extract_pdf_text, parse_promotions_from_pdf
from bankpromos.pdf_classifier import get_sources_for_bank
from bankpromos.models import UnifiedPromotion
from bankpromos.pipeline.corrections_applier import mark_needs_review, _should_mark_review
from bankpromos.corrections_service import save_review_items

logger = logging.getLogger(__name__)

PDFS_DIR = os.environ.get("BANKPROMOS_PDFS_DIR", "data/pdfs")

UENO_KEYWORDS = ["ueno", "ueno black"]


class UenoCollector(BaseCollector):
    bank_id = "ueno"
    display_name = "Ueno"

    def discover_sources(self) -> List[Source]:
        sources = []
        
        pdf_sources = get_sources_for_bank("ueno")
        
        for ps in pdf_sources:
            try:
                pdf_file = Path(ps["file"])
                if pdf_file.stat().st_size < 100:
                    continue
                
                sources.append(
                    Source(
                        source_type=SourceType.PDF,
                        url=ps["file"],
                        title=ps["filename"],
                        metadata={
                            "filename": ps["filename"],
                            "size": ps.get("size", 0),
                            "bank_detected": ps.get("bank", "ueno"),
                            "category_hint": ps.get("category_hint"),
                            "merchant_hint": ps.get("merchant_hint"),
                        },
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to process {ps['filename']}: {e}")
                continue

        logger.info(f"Ueno: discovered {len(sources)} PDF sources")
        return sources

    def collect(self, sources: Optional[List[Source]] = None) -> List[Promotion]:
        if sources is None:
            sources = self.discover_sources()

        all_promos = []
        all_review_items = []

        for source in sources:
            try:
                if source.source_type == SourceType.PDF:
                    promos, review_items = self._parse_pdf(source)
                    all_promos.extend(promos)
                    all_review_items.extend(review_items)
            except Exception as e:
                logger.warning(f"Failed to collect from {source.url}: {e}")
                continue

        if all_review_items:
            save_review_items(all_review_items)
            logger.info(f"Ueno: saved {len(all_review_items)} review items")

        logger.info(f"Ueno: collected {len(all_promos)} promotions")
        return all_promos

    def _parse_pdf(self, source: Source) -> tuple[List[Promotion], List[dict]]:
        text = extract_pdf_text(source.url)
        if not text or len(text.strip()) < 50:
            return [], []

        category_hint = source.metadata.get("category_hint")
        merchant_hint = source.metadata.get("merchant_hint")
        filename = source.metadata.get("filename", source.url)
        page_num = source.metadata.get("page", 0)

        raw_promos = parse_promotions_from_pdf(
            text,
            bank_id=self.bank_id,
            source_url=source.url,
            category_hint=category_hint,
            merchant_hint=merchant_hint,
            use_split_parser=True,
        )

        promos = []
        review_items = []
        for rp in raw_promos:
            merchant = rp.merchant_name or ""
            merchant_lower = merchant.lower().strip()
            category = rp.category or "General"
            has_discount = rp.discount_percent and rp.discount_percent > 0
            has_installment = rp.installment_count and rp.installment_count > 0
            has_cap = rp.cap_amount and rp.cap_amount > 0
            has_dates = rp.valid_from or rp.valid_to
            has_days = rp.valid_days and len(rp.valid_days) > 0
            has_conditions = bool(rp.raw_text and len(rp.raw_text) > 20)

            strength = sum([
                bool(has_discount),
                bool(has_installment),
                bool(has_cap),
                bool(has_dates),
                bool(has_days),
                bool(has_conditions),
            ])

            is_fake = any(fake in merchant_lower for fake in [
                "el reintegro del", "un reintegro del", "reintegro adicional del",
                "un descuento del", "reintegro del", "descuento del"
            ])

            is_bank = merchant_lower in ("ueno", "py_ueno")

            if is_fake or is_bank:
                if strength >= 2:
                    merchant = None
                else:
                    continue

            if category != "General" and strength >= 1:
                pass
            elif strength >= 2:
                pass
            else:
                continue

            raw_text = rp.raw_text or ""
            pattern_key = f"ueno:{filename}:{page_num}:{raw_text[:100].lower().strip()}"

            promo = Promotion(
                bank_id=self.bank_id,
                title=rp.title or f"{rp.discount_percent}% de reintegro" if rp.discount_percent else "Promo",
                merchant_name=merchant if merchant else None,
                category=rp.category,
                benefit_type=rp.benefit_type,
                discount_percent=rp.discount_percent,
                installment_count=rp.installment_count,
                valid_days=rp.valid_days or [],
                valid_from=rp.valid_from,
                valid_to=rp.valid_to,
                cap_amount=rp.cap_amount,
                payment_method=rp.payment_method,
                source_type=SourceType.PDF,
                source_url=source.url,
                raw_text=raw_text,
                needs_review=False,
                review_reason=None,
                pattern_key=pattern_key,
                metadata={
                    "extraction_confidence": rp.raw_data.get("extraction_confidence", 0),
                    "pdf_filename": filename,
                    "collector": "ueno",
                    "page": page_num,
                },
            )

            reason = _should_mark_review(promo)
            if reason:
                mark_needs_review(promo, reason)
                review_items.append({
                    "pattern_key": pattern_key,
                    "bank": self.bank_id,
                    "source_file": filename,
                    "page": page_num,
                    "detected_text": raw_text[:300],
                    "detected_merchant": merchant or "",
                    "detected_discount": float(rp.discount_percent) if rp.discount_percent else None,
                    "detected_category": rp.category or "",
                    "detected_cap": float(rp.cap_amount) if rp.cap_amount else None,
                    "detected_installments": rp.installment_count,
                    "detected_days": rp.valid_days or [],
                    "detected_payment_method": rp.payment_method,
                    "detected_conditions": rp.raw_data.get("conditions_text") if rp.raw_data else None,
                    "reason": reason,
                    "crop_path": source.metadata.get("crop_path"),
                })

            promos.append(promo)

        return promos, review_items


def get_collector(bank_id: str = "ueno") -> Optional[BaseCollector]:
    if bank_id in ["ueno", "py_ueno"]:
        return UenoCollector()
    return None


def collect_ueno() -> CollectorResult:
    collector = UenoCollector()
    sources = collector.discover_sources()
    promos = collector.collect(sources)

    return CollectorResult(
        bank_id=collector.bank_id,
        sources_discovered=sources,
        sources_parsed=len(sources),
        promotions_found=len(promos),
    )