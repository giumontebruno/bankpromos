import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import requests

from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import _is_valid_merchant_name, _contains_fuel_signal
from bankpromos.scrapers import register_scraper
from bankpromos.scrapers.base_public import BasePublicScraper

logger = logging.getLogger(__name__)

VALID_MERCHANT_INDICATORS = {
    "shell", "copetrol", "petropar", "petrobras", "enex", "pf",
    "superseis", "stock", "carrefour",
    "restaurant", "restaurante", "pizza", "sushi", "café", "bar",
}

GENERIC_TITLE_PATTERNS = {
    "obtené", "obten", "hasta", "promociones", "beneficios", "beneficio",
    "especiales", "especial", "todos", "días", "dias", "comercios",
    "adheridos", "ahorrar", "ahorro", "para vos", "para ti",
    "vigencia", "válido", "valido", "consultá", "consulta",
}


@register_scraper("py_ueno")
class UenoPromotionsScraper(BasePublicScraper):
    BENEFITS_URL = "https://www.ueno.com.py/beneficios/"

    CARD_SELECTORS = [
        '[class*="card"]',
        '[class*="promo"]',
        '[class*="beneficio"]',
        '[class*="offer"]',
        '[class*="discount"]',
        "article",
        "section",
    ]

    PDF_SELECTORS = [
        'a[href$=".pdf"]',
        'a[href*="pdf"]',
        'a[href*="beneficio"]',
        'a[href*="promo"]',
        'a[href*="catalogo"]',
        'a[href*="catalog"]',
    ]

    PAGE_URL = "https://www.ueno.com.py"

    SKIP_PHRASES: Set[str] = {
        "beneficios",
        "promociones",
        "exclusivos",
        "conoce más",
        "descargar",
        "haz click",
    }

    def _get_bank_id(self) -> str:
        return "py_ueno"

    def _is_generic_title(self, title: str) -> bool:
        title_lower = title.lower().strip()
        if not title_lower:
            return True
        if len(title_lower) < 5:
            return True
        if re.match(r"^\d+\s*%?\s*$", title_lower):
            return True
        if title_lower in GENERIC_TITLE_PATTERNS:
            return True
        for word in GENERIC_TITLE_PATTERNS:
            if title_lower == word or title_lower.startswith(f"{word} "):
                return True
        return False

    def _has_fuel_signal(self, text: str) -> bool:
        return _contains_fuel_signal(text)

    def _extract_merchant_from_card(self, card) -> Optional[str]:
        try:
            for selector in ["[class*='merchant']", "[class*='brand']", "[class*='name']", "[class*='partner']"]:
                el = card.locator(selector).first
                if el.count() > 0:
                    text = el.inner_text().strip()
                    if text and len(text) > 2 and len(text) < 50:
                        if _is_valid_merchant_name(text):
                            return text

            lines = card.inner_text().split("\n")
            for line in lines:
                line_clean = line.strip()
                if len(line_clean) >= 3 and len(line_clean) <= 40:
                    line_lower = line_clean.lower()
                    if any(indicator in line_lower for indicator in VALID_MERCHANT_INDICATORS):
                        if _is_valid_merchant_name(line_clean):
                            return line_clean

            for line in lines:
                line_clean = line.strip()
                if len(line_clean) >= 3 and len(line_clean) <= 40:
                    if _is_valid_merchant_name(line_clean):
                        return line_clean
        except Exception:
            pass
        return None

    def _scrape_promotions(self) -> List[PromotionModel]:
        page = self._ensure_page()

        self._navigate_staged(self.BENEFITS_URL)

        self._save_debug_screenshot("ueno_main")

        promotions: List[PromotionModel] = []
        dom_promos = 0
        pdf_promos = 0

        pdf_links = self._extract_pdf_links()
        
        seen_urls: Set[str] = set()
        for pdf_url in pdf_links:
            if pdf_url and pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                try:
                    from bankpromos.pdf_parser import parse_promotions_from_pdf, extract_pdf_text
                    text = extract_pdf_text(pdf_url)
                    if text:
                        pdf_results = parse_promotions_from_pdf(text, self._get_bank_id(), pdf_url)
                        if pdf_results:
                            promotions.extend(pdf_results)
                            pdf_promos += len(pdf_results)
                            self._diagnostics.promos_from_pdf = pdf_promos
                            self._diagnostics.source_used = "pdf"
                            if self.debug_mode:
                                self._save_debug_file("pdf_text.txt", text[:5000])
                except Exception as e:
                    logger.warning(f"[PDF] Parse failed: {e}")

        if pdf_promos == 0:
            html_promos = self._extract_from_page()
            if html_promos:
                promotions.extend(html_promos)
                dom_promos = len(html_promos)
                self._diagnostics.promos_from_dom = dom_promos
                if not self._diagnostics.source_used or self._diagnostics.source_used == "unknown":
                    self._diagnostics.source_used = "dom"

        if not promotions:
            self._record_fallback()
            self._diagnostics.source_used = "fallback"

        before_dedupe = len(promotions)
        deduped = self._dedupe_promotions(promotions)
        
        if not deduped:
            self._diagnostics.quality_label = "failed"
        elif any(p.merchant_name for p in deduped):
            self._diagnostics.quality_label = "actionable"
        else:
            self._diagnostics.quality_label = "generic_only"
            deduped = []

        self._finalize_diagnostics(
            url=self._diagnostics.url,
            title=page.title() or "",
            before_dedupe=before_dedupe,
            after_dedupe=len(deduped),
            body_len=len(page.locator("body").inner_text() or "") if self._page_is_alive() else 0,
        )
        logger.info(f"[{self._get_bank_id()}] source={self._diagnostics.source_used} dom={dom_promos} pdf={pdf_promos} before={before_dedupe} after={len(deduped)}")

        return deduped

    def _try_api_extraction(self) -> List[PromotionModel]:
        json_urls = [url for url in self._relevant_urls if "json" in url.lower() or "api" in url.lower()]
        for url in json_urls[:3]:
            promos = self._try_json_url(url)
            if promos:
                logger.info(f"[{self._get_bank_id()}] Found API data at: {url}")
                return promos
        return []

    def _try_json_url(self, url: str) -> List[PromotionModel]:
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or url.endswith(".json"):
                    data = response.json()
                    if isinstance(data, list):
                        return self._parse_json_promotions(data)
                    elif isinstance(data, dict) and "beneficios" in data:
                        return self._parse_json_promotions(data.get("beneficios", []))
        except Exception:
            pass
        return []

    def _parse_json_promotions(self, data: List[Dict]) -> List[PromotionModel]:
        promos = []
        for item in data:
            if isinstance(item, dict):
                title = item.get("title") or item.get("nombre") or item.get("merchant") or item.get("merchant_name", "")
                merchant = item.get("merchant") or item.get("merchant_name") or item.get("establecimiento", "")
                discount = item.get("discount") or item.get("descuento") or item.get("reintegro", 0)
                category = item.get("category") or item.get("categoria", "")

                promo = PromotionModel(
                    bank_id=self._get_bank_id(),
                    title=str(title)[:100] if title else "Promoción",
                    merchant_name=merchant if _is_valid_merchant_name(str(merchant)) else None,
                    category=category if category else "General",
                    benefit_type="reintegro" if isinstance(discount, int) and discount > 0 else None,
                    discount_percent=Decimal(str(discount)) if discount else None,
                    source_url=self.BENEFITS_URL,
                    raw_text=json.dumps(item),
                    raw_data={"source": "api", "original": item},
                )
                promos.append(promo)
        return promos

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
                    if full_url not in links:
                        links.append(full_url)
                        self._record_pdf_link()
                except Exception:
                    continue

        for url in self._relevant_urls:
            if any(ext in url.lower() for ext in [".pdf", "pdf"]):
                if url not in links:
                    links.append(url)
                    self._record_pdf_link()

        return list(set(links))

    def _extract_from_page(self) -> List[PromotionModel]:
        page = self._ensure_page()
        promotions: List[PromotionModel] = []

        for selector in self.CARD_SELECTORS:
            cards = page.locator(selector).all()
            if len(cards) > 0:
                self._card_match_count = len(cards)
                break

        for card in cards:
            try:
                title = self._extract_title_from_card(card)
                if not title:
                    continue

                if self._is_generic_title(title):
                    continue

                body = card.inner_text()
                promo = self._build_promo(title, body)
                if promo and self._has_benefit_signal(body):
                    if promo.merchant_name or self._has_fuel_signal(body):
                        promotions.append(promo)
                    else:
                        self._diagnostics.rejected_generic_count += 1
            except Exception:
                continue

        return promotions

    def _extract_from_fallback(self) -> List[PromotionModel]:
        return []

    def _extract_title_from_card(self, card) -> Optional[str]:
        try:
            for tag in ["h2", "h3", "h4", "h5"]:
                title = card.locator(tag).first.inner_text().strip()
                if title:
                    return title
            title = card.locator("[class*='title']").first.inner_text().strip()
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

    def _extract_merchant_from_text(self, text: str) -> Optional[str]:
        lines = text.split("\n")

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            if len(line_clean) < 3 or len(line_clean) > 40:
                continue
            if _is_valid_merchant_name(line_clean):
                return line_clean

        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 3:
                continue
            line_lower = line_clean.lower()
            if any(indicator in line_lower for indicator in VALID_MERCHANT_INDICATORS):
                return line_clean

        return None

    def _parse_pdf_promotions(self, pdf_url: str) -> List[PromotionModel]:
        try:
            from bankpromos.pdf_parser import extract_pdf_text, parse_promotions_from_pdf
            
            text = extract_pdf_text(pdf_url)
            if not text:
                return []
            
            return parse_promotions_from_pdf(text, self._get_bank_id(), pdf_url)
        except Exception as e:
            logger.warning(f"PDF parse failed: {e}")
            return []

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
        return f"{p.bank_id}:{merchant}:{discount}"

    def _build_promo_from_text(self, text: str) -> Optional[PromotionModel]:
        lines = text.split("\n")
        title = lines[0] if lines else text[:50]

        merchant = self._extract_merchant_from_text(text)

        discount_percent: Optional[Decimal] = None
        installment_count: Optional[int] = None
        valid_days: List[str] = []
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
            "lunes": "lunes", "martes": "martes", "miercoles": "miércoles",
            "jueves": "jueves", "viernes": "viernes", "sabado": "sábado",
            "sabados": "sábado", "domingo": "domingo", "domingos": "domingo",
        }
        for day_key, day_norm in days_map.items():
            if day_key in text.lower():
                valid_days.append(day_norm)

        dates = self._parse_dates(text)

        if not any([discount_percent, installment_count, valid_days, dates[0], dates[1]]):
            return None

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title[:100],
            merchant_name=merchant,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            installment_count=installment_count,
            valid_days=sorted(list(set(valid_days))),
            valid_from=dates[0],
            valid_to=dates[1],
            source_url=self.BENEFITS_URL,
            raw_text=text[:500],
            raw_data={"source": "pdf"},
        )

    def _build_promo(self, title: str, detail: str) -> Optional[PromotionModel]:
        full_text = f"{title}. {detail}"

        merchant = self._extract_merchant_from_text(detail)

        if not merchant:
            merchant = self._extract_merchant_from_text(full_text)

        pct_match = re.search(r"(\d{1,2})\s*%", full_text, re.I)
        discount_percent: Optional[Decimal] = Decimal(pct_match.group(1)) if pct_match else None

        benefit_type = None
        if "reintegro" in full_text.lower():
            benefit_type = "reintegro"
        elif "descuento" in full_text.lower():
            benefit_type = "descuento"

        category = self._infer_category(title, detail)

        days_map = {
            "lunes": "lunes", "martes": "martes", "miercoles": "miércoles",
            "jueves": "jueves", "viernes": "viernes", "sabado": "sábado",
            "sabados": "sábado", "domingo": "domingo", "domingos": "domingo",
        }
        valid_days = []
        for day_key, day_norm in days_map.items():
            if day_key in full_text.lower():
                valid_days.append(day_norm)

        dates = self._parse_dates(full_text)

        if not any([discount_percent, valid_days, dates[0], dates[1]]):
            return None

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title[:100],
            merchant_name=merchant,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            installment_count=None,
            valid_days=sorted(list(set(valid_days))),
            valid_from=dates[0],
            valid_to=dates[1],
            source_url=self.BENEFITS_URL,
            raw_text=full_text[:500],
            raw_data={"source": "html"},
        )

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
            (["combustible", "estacion", "shell", "petro", "copetrol", "nafta", "diesel", "enex"], "Combustible"),
            (["supermercado", "carrito", "stock", "superseis"], "Supermercados"),
            (["gastr", "restaur", "bar", "coffee", "pizza", "sushi"], "Gastronomía"),
            (["ropa", "indumentaria", "moda", "zapateria"], "Indumentaria"),
            (["tecnología", "celular", "tech", "smart"], "Tecnología"),
            (["universidad", "curso", "educacion", "estudio"], "Educación"),
            (["farmacia", "salud", "clinica"], "Salud"),
            (["hogar", "muebleria", "ferreteria"], "Hogar"),
            (["viaje", "vacaciones", "hotel"], "Viajes"),
        ]

        for keywords, category in rules:
            if any(kw in txt for kw in keywords):
                return category

        return "General"