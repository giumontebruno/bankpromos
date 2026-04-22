import logging
import re
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Set
from urllib.parse import urljoin

import requests

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from bankpromos.core.models import PromotionModel
from bankpromos.scrapers import register_scraper
from bankpromos.scrapers.base_public import BasePublicScraper

logger = logging.getLogger(__name__)


@register_scraper("py_bnf")
class BnfPromotionsScraper(BasePublicScraper):
    BENEFITS_URL = "https://www.bnf.com.py/beneficios"

    CARD_SELECTORS = [
        '[class*="card"]',
        '[class*="promo"]',
        '[class*="beneficio"]',
        '[class*="offer"]',
        '[class*="discount"]',
    ]

    PDF_SELECTORS = [
        'a[href$=".pdf"]',
        'a[href*="pdf"]',
        'a[href*="beneficio"]',
        'a[href*="promo"]',
    ]

    PAGE_URL = "https://www.bnf.com.py"

    SKIP_PHRASES: Set[str] = {
        "beneficios",
        "promociones",
        "exclusivos",
        "conoce más",
        "descargar",
        "haz click",
    }

    def _get_bank_id(self) -> str:
        return "py_bnf"

    def _scrape_promotions(self) -> List[PromotionModel]:
        page = self._ensure_page()
        self._navigate(self.BENEFITS_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        self._save_debug_screenshot("bnf_main")

        promotions: List[PromotionModel] = []
        before_dedupe = 0

        pdf_links = self._extract_pdf_links()
        seen_urls: Set[str] = set()
        for pdf_url in pdf_links:
            if pdf_url and pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                promotions.extend(self._parse_pdf_promotions(pdf_url))

        html_promos = self._extract_from_page()
        promotions.extend(html_promos)

        before_dedupe = len(promotions)
        deduped = self._dedupe_promotions(promotions)

        self._finalize_diagnostics(
            url=self._diagnostics.url,
            title=page.title() or "",
            before_dedupe=before_dedupe,
            after_dedupe=len(deduped),
            body_len=len(page.locator("body").inner_text() or ""),
        )
        logger.info(f"[{self._get_bank_id()}] url={self._diagnostics.url} title={self._diagnostics.title[:30]} cards={self._card_match_count} pdfs={self._pdf_link_count} fallback={self._fallback_ran} before={before_dedupe} after={len(deduped)}")

        return deduped

    def _extract_pdf_links(self) -> List[str]:
        page = self._ensure_page()
        links: List[str] = []

        for selector in self.PDF_SELECTORS:
            els = page.locator(selector).all()
            for el in els:
                try:
                    href = el.get_attribute("href")
                    if not href:
                        continue
                    full_url = urljoin(self.PAGE_URL, href) if not href.startswith("http") else href
                    links.append(full_url)
                    self._record_pdf_link()
                except Exception:
                    continue

        return list(set(links))

    def _extract_from_page(self) -> List[PromotionModel]:
        page = self._ensure_page()
        promotions: List[PromotionModel] = []

        selector = ", ".join(self.CARD_SELECTORS)
        cards = page.locator(selector).all()
        self._card_match_count = len(cards)

        for card in cards:
            try:
                title = self._extract_title_from_card(card)
                if not title or len(title) < 3:
                    continue

                body = card.inner_text()
                promo = self._build_promo(title, body)
                if promo and self._has_benefit_signal(body):
                    promotions.append(promo)
            except Exception:
                continue

        if not promotions:
            self._record_fallback()
            body_text = page.locator("body").inner_text()
            promotions = self._extract_from_text(body_text)

        return promotions

    def _extract_title_from_card(self, card) -> Optional[str]:
        try:
            title = card.locator("h2, h3, h4, h5, [class*='title'], [class*='name']").first.inner_text().strip()
            if title:
                return title
            first_line = card.inner_text().split("\n")[0].strip()
            if first_line and len(first_line) > 2:
                return first_line
        except Exception:
            pass
        return None

    def _has_benefit_signal(self, text: str) -> bool:
        text_lower = text.lower()
        signals = [
            r"\d{1,2}\s*%",
            r"\d{1,2}\s*cuotas?",
            r"reintegro",
            r"descuento",
            r"vigencia",
            r"válido",
            r"valido",
        ]
        for signal in signals:
            if re.search(signal, text_lower):
                return True
        return False

    def _extract_from_text(self, text: str) -> List[PromotionModel]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        promotions: List[PromotionModel] = []

        current_title: Optional[str] = None
        buffer: List[str] = []

        for line in lines:
            if line.lower() in self.SKIP_PHRASES:
                continue
            if len(line) < 50 and len(line) > 3:
                if current_title and buffer:
                    detail = " ".join(buffer)
                    if self._has_benefit_signal(detail):
                        promo = self._build_promo(current_title, detail)
                        if promo:
                            promotions.append(promo)
                current_title = line
                buffer = []
            else:
                if current_title:
                    buffer.append(line)

        if current_title and buffer:
            detail = " ".join(buffer)
            if self._has_benefit_signal(detail):
                promo = self._build_promo(current_title, detail)
                if promo:
                    promotions.append(promo)

        return promotions

    def _parse_pdf_promotions(self, pdf_url: str) -> List[PromotionModel]:
        if not pdfplumber:
            return []

        try:
            response = requests.get(pdf_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if len(response.content) < 1000:
                return []
        except Exception:
            return []

        pdf_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(response.content)
                pdf_path = f.name

            promotions: List[PromotionModel] = []

            with pdfplumber.open(pdf_path) as pdf:
                for pdf_page in pdf.pages:
                    text = pdf_page.extract_text()
                    if not text:
                        continue

                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    if not lines:
                        continue

                    promo_texts = self._split_pdf_into_blocks(lines)
                    for block in promo_texts:
                        if self._has_benefit_signal(block):
                            promo = self._build_promo_from_text(block)
                            if promo:
                                promotions.append(promo)

            return promotions

        except Exception:
            return []
        finally:
            if pdf_path:
                try:
                    import os
                    os.unlink(pdf_path)
                except Exception:
                    pass

    def _split_pdf_into_blocks(self, lines: List[str]) -> List[str]:
        blocks: List[str] = []
        current_block: List[str] = []

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                if current_block:
                    blocks.append(" ".join(current_block))
                    current_block = []
                continue

            if re.match(r"^[A-Z][A-Za-z\s\d&'-]{2,30}$", line_clean) and len(line_clean) < 40:
                if current_block:
                    blocks.append(" ".join(current_block))
                current_block = [line_clean]
            else:
                current_block.append(line_clean)

        if current_block:
            blocks.append(" ".join(current_block))

        return blocks

    def _dedupe_promotions(self, promos: List[PromotionModel]) -> List[PromotionModel]:
        if not promos:
            return []

        seen: Set[str] = set()
        unique: List[PromotionModel] = []

        for p in promos:
            key = self._promo_key(p)
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _promo_key(self, p: PromotionModel) -> str:
        merchant = (p.merchant_name or p.title or "").lower().strip()
        discount = str(p.discount_percent or "")
        cuotas = str(p.installment_count or "")
        return f"{p.bank_id}:{merchant}:{discount}:{cuotas}"

    def _build_promo_from_text(self, text: str) -> Optional[PromotionModel]:
        lines = text.split("\n")
        title = lines[0] if lines else text[:50]

        discount_percent: Optional[Decimal] = None
        installment_count: Optional[int] = None
        valid_days: List[str] = []
        valid_from: Optional[datetime.date] = None
        valid_to: Optional[datetime.date] = None
        benefit_type: Optional[str] = None
        category = self._infer_category(title, text)

        pct_match = re.search(r"(\d{1,2})\s*%", text, re.I)
        if pct_match:
            discount_percent = Decimal(pct_match.group(1))
            if "reintegro" in text.lower():
                benefit_type = "reintegro"
            elif "descuento" in text.lower():
                benefit_type = "descuento"

        cuotas_match = re.search(r"(\d{1,2})\s*cuotas?", text, re.I)
        if cuotas_match:
            installment_count = int(cuotas_match.group(1))
            if not benefit_type:
                benefit_type = "cuotas"

        days_map = {
            "lunes": "lunes",
            "martes": "martes",
            "miercoles": "miércoles",
            "miércoles": "miércoles",
            "jueves": "jueves",
            "viernes": "viernes",
            "sabado": "sábado",
            "sábados": "sábado",
            "sábado": "sábado",
            "domingo": "domingo",
            "domingos": "domingo",
        }
        for day_key, day_norm in days_map.items():
            if day_key in text.lower():
                valid_days.append(day_norm)

        dates = self._parse_dates(text)
        if dates:
            valid_from, valid_to = dates

        if not any([discount_percent, installment_count, valid_days, valid_from, valid_to]):
            return None

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title[:100],
            merchant_name=title[:100],
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            installment_count=installment_count,
            valid_days=sorted(list(set(valid_days))),
            valid_from=valid_from,
            valid_to=valid_to,
            source_url=self.BENEFITS_URL,
            raw_text=text[:500],
            raw_data={"source": "pdf"},
        )

    def _build_promo(self, title: str, detail: str) -> Optional[PromotionModel]:
        return self._build_promo_from_text(f"{title}. {detail}")

    def _parse_dates(self, text: str):
        valid_from: Optional[datetime.date] = None
        valid_to: Optional[datetime.date] = None

        date_match = re.search(
            r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:al|-)\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
            text,
            re.I,
        )
        if date_match:
            try:
                d1, m1, y1 = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                d2, m2, y2 = int(date_match.group(4)), int(date_match.group(5)), int(date_match.group(6))
                y1 = 2000 + y1 if y1 < 100 else y1
                y2 = 2000 + y2 if y2 < 100 else y2
                if y1 <= 2100:
                    valid_from = datetime(y1, m1, d1).date()
                if y2 <= 2100:
                    valid_to = datetime(y2, m2, d2).date()
            except Exception:
                pass

        return valid_from, valid_to

    def _infer_category(self, title: str, detail: str) -> Optional[str]:
        txt = f"{title} {detail}".lower()

        rules = [
            (["supermercado", "carrito", "stock", "superseis"], "Supermercados"),
            (["gastr", "restaur", "bar", "coffee", "pizza"], "Gastronomía"),
            (["ropa", "indumentaria", "moda"], "Indumentaria"),
            (["tecnología", "celular", "tech"], "Tecnología"),
            (["universidad", "curso", "educacion"], "Educación"),
            (["farmacia", "salud", "clinica"], "Salud"),
            (["combustible", "estacion", "shell"], "Combustible"),
            (["hogar", "muebleria", "ferreteria"], "Hogar"),
            (["viaje", "vacaciones", "hotel"], "Viajes"),
        ]

        for keywords, category in rules:
            if any(kw in txt for kw in keywords):
                return category

        return "General"