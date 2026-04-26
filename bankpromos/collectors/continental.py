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
from bankpromos.pipeline.corrections_applier import mark_needs_review, _should_mark_review
from bankpromos.corrections_service import save_review_items, load_review_items

logger = logging.getLogger(__name__)

PDFS_DIR = os.environ.get("BANKPROMOS_PDFS_DIR", "data/pdfs")


class ContinentalCollector(BaseCollector):
    bank_id = "continental"
    display_name = "Banco Continental"

    def discover_sources(self) -> List[Source]:
        sources = []
        
        pdf_sources = get_sources_for_bank("continental")
        
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
                            "bank_detected": ps.get("bank", "continental"),
                            "category_hint": ps.get("category_hint"),
                            "merchant_hint": ps.get("merchant_hint"),
                        },
                    )
                )
            except Exception as e:
                logger.warning(f"Failed: {e}")
                continue
        
        if not sources:
            pdfs_dir = Path(PDFS_DIR)
            if pdfs_dir.exists():
                for pdf_file in sorted(pdfs_dir.glob("*.pdf")):
                    try:
                        if pdf_file.stat().st_size < 100:
                            continue
                        fname_lower = pdf_file.name.lower()
                        if "guia" in fname_lower or "continental" in fname_lower:
                            sources.append(
                                Source(
                                    source_type=SourceType.PDF,
                                    url=str(pdf_file),
                                    title=pdf_file.name,
                                    metadata={
                                        "filename": pdf_file.name,
                                        "size": pdf_file.stat().st_size,
                                        "bank_detected": "continental",
                                    },
                                )
                            )
                    except Exception:
                        continue

        logger.info(f"Continental: discovered {len(sources)} sources")
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
                import traceback
                logger.warning(f"Failed to collect from {source.url}: {e}")
                continue

        if all_review_items:
            save_review_items(all_review_items)
            logger.info(f"Continental: saved {len(all_review_items)} review items")

        logger.info(f"Continental: collected {len(all_promos)} promotions")
        return all_promos

    def _parse_pdf(self, source: Source) -> tuple[List[Promotion], List[dict]]:
        try:
            text = extract_pdf_text(source.url)
        except Exception as e:
            logger.warning(f"PDF text extraction failed for {source.url}: {e}")
            return [], []

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
        )

        promos = []
        review_items = []
        for rp in raw_promos:
            if not rp.merchant_name and not rp.discount_percent:
                continue

            raw_text = rp.raw_text or ""
            pattern_key = f"continental:{filename}:{page_num}:{raw_text[:100].lower().strip()}"

            promo = Promotion(
                bank_id=self.bank_id,
                title=rp.title or f"{rp.discount_percent}% de reintegro" if rp.discount_percent else "Promo",
                merchant_name=rp.merchant_name,
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
                    "extraction_confidence": rp.raw_data.get("extraction_confidence", 0) if rp.raw_data else 0,
                    "pdf_filename": filename,
                    "collector": "continental",
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
                    "detected_merchant": rp.merchant_name or "",
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


def get_collector(bank_id: str = "continental") -> Optional[BaseCollector]:
    if bank_id in ["continental", "py_continental"]:
        return ContinentalCollector()
    return None


def collect_continental() -> CollectorResult:
    collector = ContinentalCollector()
    sources = collector.discover_sources()
    promos = collector.collect(sources)

    return CollectorResult(
        bank_id=collector.bank_id,
        sources_discovered=sources,
        sources_parsed=len(sources),
        promotions_found=len(promos),
    )