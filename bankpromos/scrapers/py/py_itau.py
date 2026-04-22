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

GENERIC_TITLE_WORDS = {
    "beneficio", "beneficios", "promocion", "promociones", "descuento",
    "oferta", "exclusivo", "exclusivos", "especial", "especiales",
    "obtene", "obten", "hasta", "para vos", "para ti",
    "comercios", "adheridos", "todos", "generales", "general",
}


@register_scraper("py_itau")
class ItauPromotionsScraper(BasePublicScraper):
    BENEFITS_URL = "https://www.itau.com.py/beneficios"

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
    ]

    SKIP_PHRASES: Set[str] = {
        "beneficios",
        "promociones",
        "exclusivos",
        "conoce más",
        "haz click",
    }

    def _get_bank_id(self) -> str:
        return "py_itau"

    def _is_generic_title(self, title: str) -> bool:
        title_lower = title.lower().strip()
        if not title_lower:
            return True
        if len(title_lower) < 4:
            return True
        if re.match(r"^\d+\s*%?\s*$", title_lower):
            return True
        if title_lower in GENERIC_TITLE_WORDS:
            return True
        generic_starts = ["beneficios para", "obtene ", "hasta "]
        for word in generic_starts:
            if title_lower.startswith(word):
                return True
        for word in GENERIC_TITLE_WORDS:
            if title_lower.endswith(f" {word}"):
                return True
        return False

    def _has_real_merchant(self, text: str) -> bool:
        text_lower = text.lower()
        if any(indicator in text_lower for indicator in VALID_MERCHANT_INDICATORS):
            return True
        return False

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

        self._save_debug_screenshot("itau_main")

        promotions: List[PromotionModel] = []
        dom_promos = 0
        pdf_promos = 0

        api_promos = self._try_api_extraction()
        if api_promos:
            promotions.extend(api_promos)
            self._diagnostics.promos_from_api = len(api_promos)
            self._diagnostics.source_used = "api"

        pdf_links = self._extract_pdf_links()
        seen_urls: Set[str] = set()
        for pdf_url in pdf_links:
            if pdf_url and pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                pdf_results = self._parse_pdf_promotions(pdf_url)
                if pdf_results:
                    promotions.extend(pdf_results)
                    pdf_promos += len(pdf_results)

        if pdf_promos > 0:
            self._diagnostics.promos_from_pdf = pdf_promos
            if not self._diagnostics.source_used or self._diagnostics.source_used == "unknown":
                self._diagnostics.source_used = "pdf"

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
            fallback_promos = self._extract_from_fallback()
            promotions.extend(fallback_promos)

        before_dedupe = self._extracted_count if self._extracted_count > 0 else len(promotions)
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
                    elif isinstance(data, dict):
                        for key in ["beneficios", "promociones", "promos", "data"]:
                            if key in data:
                                return self._parse_json_promotions(data[key])
        except Exception:
            pass
        return []

    def _parse_json_promotions(self, data: List[Dict]) -> List[PromotionModel]:
        promos = []
        for item in data:
            if isinstance(item, dict):
                title = item.get("title") or item.get("nombre") or item.get("merchant", "")
                merchant = item.get("merchant") or item.get("establecimiento", "")
                discount = item.get("discount") or item.get("descuento") or item.get("reintegro", 0)
                category = item.get("category") or item.get("categoria", "")

                if not merchant and title and self._is_generic_title(str(title)):
                    continue

                promo = PromotionModel(
                    bank_id=self._get_bank_id(),
                    title=str(title)[:100] if title else "Promoción",
                    merchant_name=merchant if _is_valid_merchant_name(str(merchant)) else None,
                    category=category if category else "General",
                    benefit_type="reintegro" if isinstance(discount, (int, float)) and discount > 0 else None,
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
                    full_url = urljoin("https://www.itau.com.py", href) if not href.startswith("http") else href
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

    def _parse_pdf_promotions(self, pdf_url: str) -> List[PromotionModel]:
        try:
            response = requests.get(pdf_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if len(response.content) < 1000:
                return []
        except Exception:
            return []

        try:
            import pdfplumber
        except ImportError:
            return []

        pdf_path = ""
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(response.content)
                pdf_path = f.name

            promotions: List[PromotionModel] = []

            with pdfplumber.open(pdf_path) as pdf:
                for pdf_page in pdf.pages:
                    text = pdf_page.extract_text()
                    if not text:
                        continue
                    promo = self._build_promo_from_text(text)
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
                if not title or len(title) < 3:
                    continue

                if self._is_generic_title(title):
                    continue

                body = card.inner_text()
                promo = self._build_promo(title, body)
                if promo and self._has_benefit_signal(body):
                    if promo.merchant_name or _contains_fuel_signal(body) or self._has_real_merchant(body):
                        promotions.append(promo)
                    else:
                        self._diagnostics.rejected_generic_count += 1
            except Exception:
                continue

        self._record_extracted(len(promotions))
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
            r"hasta\s+\d+",
        ]
        for signal in signals:
            if re.search(signal, text_lower):
                return True
        return False

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
        if not lines:
            return None

        title = lines[0][:100]
        if self._is_generic_title(title):
            title = "Promoción Itaú"

        merchant = self._extract_merchant_from_text(text)
        if not merchant and not _contains_fuel_signal(text) and not self._has_real_merchant(text):
            return None

        pct_match = re.search(r"(\d{1,2})\s*%", text, re.I)
        discount_percent = Decimal(pct_match.group(1)) if pct_match else None

        benefit_type = None
        if "reintegro" in text.lower():
            benefit_type = "reintegro"
        elif "descuento" in text.lower():
            benefit_type = "descuento"

        category = self._infer_category(title, text)

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title,
            merchant_name=merchant,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            source_url=self.BENEFITS_URL,
            raw_text=text[:500],
            raw_data={"source": "pdf"},
        )

    def _build_promo(self, title: str, detail: str) -> Optional[PromotionModel]:
        full_text = f"{title}. {detail}"

        if self._is_generic_title(title):
            if not _contains_fuel_signal(full_text) and not self._has_real_merchant(full_text):
                return None

        merchant_name = self._extract_merchant_from_text(full_text)

        pct_match = re.search(r"(\d{1,2})\s*%", full_text, re.I)
        discount_percent: Optional[Decimal] = Decimal(pct_match.group(1)) if pct_match else None

        benefit_type = None
        if "reintegro" in full_text.lower():
            benefit_type = "reintegro"
        elif "descuento" in full_text.lower():
            benefit_type = "descuento"

        category = self._infer_category(title, detail)

        if not any([discount_percent, merchant_name]):
            return None

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title,
            merchant_name=merchant_name,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            source_url=self.BENEFITS_URL,
            raw_text=full_text,
            raw_data={"source": "html"},
        )

    def _extract_merchant_from_text(self, text: str) -> Optional[str]:
        lines = text.split("\n")
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

        return None

    def _infer_category(self, title: str, detail: str) -> Optional[str]:
        txt = f"{title} {detail}".lower()

        rules = [
            (["combustible", "estacion", "shell", "petro", "copetrol", "nafta", "diesel", "enex"], "Combustible"),
            (["supermercado", "carrito", "stock"], "Supermercados"),
            (["gastr", "restaur", "bar", "coffee", "pizza"], "Gastronomía"),
            (["ropa", "indumentaria", "moda"], "Indumentaria"),
            (["tecnología", "celular", "tech"], "Tecnología"),
            (["universidad", "curso", "educacion"], "Educación"),
            (["farmacia", "salud", "clinica"], "Salud"),
            (["hogar", "muebleria", "ferreteria"], "Hogar"),
            (["viaje", "vacaciones", "hotel"], "Viajes"),
        ]

        for keywords, category in rules:
            if any(kw in txt for kw in keywords):
                return category

        return "General"