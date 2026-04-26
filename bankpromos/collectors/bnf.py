import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from bankpromos.collectors.base import (
    BaseCollector,
    Promotion,
    Source,
    SourceType,
    CollectorResult,
)
from bankpromos.scrapers import get_scraper

logger = logging.getLogger(__name__)

PDFS_DIR = os.environ.get("BANKPROMOS_PDFS_DIR", "data/pdfs")

BNF_API = "https://club.bnf.com.py/api/benefits"


class BnfCollector(BaseCollector):
    bank_id = "bnf"
    display_name = "Banco BNF"

    def discover_sources(self) -> List[Source]:
        sources = []
        pdfs_dir = Path(PDFS_DIR)

        if pdfs_dir.exists():
            for pdf_file in sorted(pdfs_dir.glob("*.pdf")):
                try:
                    if pdf_file.stat().st_size < 100:
                        continue

                    filename_lower = pdf_file.name.lower()

                    if "bnf" in filename_lower:
                        sources.append(
                            Source(
                                source_type=SourceType.PDF,
                                url=str(pdf_file),
                                title=pdf_file.name,
                                metadata={
                                    "filename": pdf_file.name,
                                    "size": pdf_file.stat().st_size,
                                    "bank_detected": "bnf",
                                },
                            )
                        )
                except Exception:
                    continue

        sources.append(
            Source(
                source_type=SourceType.API,
                url=BNF_API,
                title="BNF API",
                metadata={"source": "api"},
            )
        )

        sources.append(
            Source(
                source_type=SourceType.HTML,
                url="https://www.bnf.com.py/beneficios",
                title="BNF Beneficios HTML",
                metadata={"source": "html"},
            )
        )

        logger.info(f"BNF: discovered {len(sources)} sources")
        return sources

    def collect(self, sources: Optional[List[Source]] = None) -> List[Promotion]:
        if sources is None:
            sources = self.discover_sources()

        all_promos = []

        api_sources = [s for s in sources if s.source_type == SourceType.API]
        html_sources = [s for s in sources if s.source_type == SourceType.HTML]
        pdf_sources = [s for s in sources if s.source_type == SourceType.PDF]

        for source in api_sources:
            try:
                api_promos = self._fetch_api()
                all_promos.extend(api_promos)
            except Exception as e:
                logger.warning(f"BNF API error: {e}")

        if html_sources and not all_promos:
            try:
                html_promos = self._scrape_html()
                all_promos.extend(html_promos)
            except Exception as e:
                logger.warning(f"BNF HTML error: {e}")

        for source in pdf_sources:
            try:
                pdf_promos = self._parse_pdf(source)
                all_promos.extend(pdf_promos)
            except Exception as e:
                logger.warning(f"BNF PDF error: {e}")

        logger.info(f"BNF: collected {len(all_promos)} promos")
        return all_promos

    def _fetch_api(self) -> List[Promotion]:
        promos = []

        try:
            scraper = get_scraper("py_bnf", debug_mode=False)
            raw_promos = scraper.scrape()

            for rp in raw_promos:
                promo = Promotion(
                    bank_id=self.bank_id,
                    title=rp.title,
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
                    source_type=SourceType.API,
                    source_url=rp.source_url or "",
                    raw_text=rp.raw_text,
                    metadata={"collector": "bnf", "scraper": "py_bnf"},
                )
                promos.append(promo)
        except Exception as e:
            logger.warning(f"BNF API fetch failed: {e}")

        return promos

    def _scrape_html(self) -> List[Promotion]:
        promos = []

        try:
            scraper = get_scraper("py_bnf", debug_mode=False)
            raw_promos = scraper.scrape()

            for rp in raw_promos:
                promo = Promotion(
                    bank_id=self.bank_id,
                    title=rp.title,
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
                    source_type=SourceType.HTML,
                    source_url=rp.source_url or "",
                    raw_text=rp.raw_text,
                    metadata={"collector": "bnf", "scraper": "py_bnf"},
                )
                promos.append(promo)
        except Exception as e:
            logger.warning(f"BNF HTML scrape failed: {e}")

        return promos

    def _parse_pdf(self, source: Source) -> List[Promotion]:
        from bankpromos.pdf_parser import extract_pdf_text, parse_promotions_from_pdf

        text = extract_pdf_text(source.url)
        if not text or len(text.strip()) < 50:
            return []

        raw_promos = parse_promotions_from_pdf(
            text,
            bank_id=self.bank_id,
            source_url=source.url,
        )

        promos = []
        for rp in raw_promos:
            if not rp.merchant_name and not rp.discount_percent:
                continue

            promo = Promotion(
                bank_id=self.bank_id,
                title=rp.title or f"{rp.discount_percent}% reintegro" if rp.discount_percent else "Promo",
                merchant_name=rp.merchant_name,
                category=rp.category,
                benefit_type=rp.benefit_type,
                discount_percent=rp.discount_percent,
                installment_count=rp.installment_count,
                valid_days=rp.valid_days or [],
                cap_amount=rp.cap_amount,
                source_type=SourceType.PDF,
                source_url=source.url,
                raw_text=rp.raw_text,
                metadata={"collector": "bnf"},
            )
            promos.append(promo)

        return promos


def get_collector(bank_id: str = "bnf") -> Optional[BaseCollector]:
    if bank_id in ["bnf", "py_bnf"]:
        return BnfCollector()
    return None


def collect_bnf() -> CollectorResult:
    collector = BnfCollector()
    sources = collector.discover_sources()
    promos = collector.collect(sources)

    return CollectorResult(
        bank_id=collector.bank_id,
        sources_discovered=sources,
        sources_parsed=len(sources),
        promotions_found=len(promos),
    )