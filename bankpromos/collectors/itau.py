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


class ItauCollector(BaseCollector):
    bank_id = "itau"
    display_name = "Itau"

    def discover_sources(self) -> List[Source]:
        sources = []
        pdfs_dir = Path(PDFS_DIR)

        if not pdfs_dir.exists():
            return sources

        for pdf_file in sorted(pdfs_dir.glob("*.pdf")):
            try:
                if pdf_file.stat().st_size < 100:
                    continue

                filename_lower = pdf_file.name.lower()

                if "itau" in filename_lower:
                    sources.append(
                        Source(
                            source_type=SourceType.PDF,
                            url=str(pdf_file),
                            title=pdf_file.name,
                            metadata={
                                "filename": pdf_file.name,
                                "size": pdf_file.stat().st_size,
                                "bank_detected": "itau",
                            },
                        )
                    )
            except Exception:
                continue

        sources.append(
            Source(
                source_type=SourceType.HTML,
                url="https://www.itau.com.py/beneficios",
                title="Itau Beneficios HTML",
                metadata={"source": "html"},
            )
        )

        logger.info(f"Itau: discovered {len(sources)} sources")
        return sources

    def collect(self, sources: Optional[List[Source]] = None) -> List[Promotion]:
        if sources is None:
            sources = self.discover_sources()

        all_promos = []

        html_sources = [s for s in sources if s.source_type == SourceType.HTML]

        if html_sources:
            try:
                html_promos = self._scrape_html()
                all_promos.extend(html_promos)
            except Exception as e:
                logger.warning(f"Itau HTML scrape error: {e}")

        for source in sources:
            if source.source_type == SourceType.PDF:
                try:
                    pdf_promos = self._parse_pdf(source)
                    all_promos.extend(pdf_promos)
                except Exception as e:
                    logger.warning(f"Itau PDF parse error: {e}")

        logger.info(f"Itau: collected {len(all_promos)} promos")
        return all_promos

    def _scrape_html(self) -> List[Promotion]:
        promos = []
        
        CATEGORY_KEYWORDS = {
            "Combustible": ["combustible", "nafta", "gasolina", "diesel", "shell", "copetrol", "petropar", "enex"],
            "Supermercados": ["supermercado", "stock", "carrefour", "superseis", "art", "arete", "biggie", "supermax"],
            "Gastronomía": ["restaurante", "bar", "comida", "burger", "subway", "pizza", "sushi", "mcdonald", "café", "helado"],
            "Indumentaria": ["ropa", "tienda", "moda", "indumentaria", "zara", "mango", "levis"],
            "Tecnología": ["tecnología", "celular", "gadget", "apple", "samsung", "electro"],
            "Viajes": ["viaje", "hotel", "turismo", "aerolínea", "vuelo", "airbnb"],
            "Belleza": ["belleza", "spa", "peluquería", "cosmético"],
            "Salud": ["farmacia", "salud", "médico", "clínica", "farmacenter"],
            "Educación": ["educación", "colegio", "universidad", "curso", "librería", "libro"],
        }
        
        FAKE_WORDS = {"beneficio", "beneficios", "promoción", "promociones", "exclusivo", "itau", "ueno", "sudameris", "haz click", "conoce", "todos los", "comercios adheridos"}
        
        try:
            scraper = get_scraper("py_itau", debug_mode=False)
            raw_promos = scraper.scrape()

            for rp in raw_promos:
                if not rp.title or len(rp.title) < 5:
                    continue
                
                title_lower = rp.title.lower()
                raw_lower = (rp.raw_text or "").lower()
                
                if any(w in title_lower for w in FAKE_WORDS):
                    continue
                
                if len(title_lower) < 10:
                    continue
                
                merchant = rp.merchant_name or ""
                merchant_lower = merchant.lower()
                
                if merchant_lower in ("itau", "ueno", "sudameris", "beneficios", "banco", "banco itau", ""):
                    merchant = None
                
                if any(fake in merchant_lower for fake in ["reintegro del", "un descuento", "beneficio del", "los meses", "disfrut"]):
                    merchant = None
                
                category = rp.category or "General"
                if category == "General":
                    for cat, keywords in CATEGORY_KEYWORDS.items():
                        if any(kw in title_lower or kw in raw_lower for kw in keywords):
                            category = cat
                            break
                
                has_discount = rp.discount_percent and rp.discount_percent > 0
                has_installment = rp.installment_count and rp.installment_count > 0
                has_cap = rp.cap_amount and rp.cap_amount > 0
                has_days = rp.valid_days and len(rp.valid_days) > 0
                has_conditions = bool(rp.raw_text and len(rp.raw_text) > 30)
                has_merchant = merchant and len(merchant) >= 2
                
                strength = sum([bool(has_discount), bool(has_installment), bool(has_cap), bool(has_days), bool(has_conditions), bool(has_merchant)])
                
                if category == "General" and strength < 2:
                    continue
                if category != "General" and strength < 1:
                    continue
                if strength == 0:
                    continue
                
                promo = Promotion(
                    bank_id=self.bank_id,
                    title=rp.title,
                    merchant_name=merchant,
                    category=category,
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
                    metadata={"collector": "itau", "scraper": "py_itau"},
                )
                promos.append(promo)
        except Exception as e:
            logger.warning(f"Itau scrape failed: {e}")

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
            use_split_parser=True,
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
                metadata={"collector": "itau"},
            )
            promos.append(promo)

        return promos


def get_collector(bank_id: str = "itau") -> Optional[BaseCollector]:
    if bank_id in ["itau", "py_itau"]:
        return ItauCollector()
    return None


def collect_itau() -> CollectorResult:
    collector = ItauCollector()
    sources = collector.discover_sources()
    promos = collector.collect(sources)

    return CollectorResult(
        bank_id=collector.bank_id,
        sources_discovered=sources,
        sources_parsed=len(sources),
        promotions_found=len(promos),
    )