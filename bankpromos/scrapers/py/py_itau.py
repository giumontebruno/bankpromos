import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Set

from bankpromos.core.models import PromotionModel
from bankpromos.scrapers import register_scraper
from bankpromos.scrapers.base_public import BasePublicScraper


@register_scraper("py_itau")
class ItauPromotionsScraper(BasePublicScraper):
    BENEFITS_URL = "https://www.itau.com.py/beneficios"

    CARD_SELECTORS = [
        '[class*="card"]',
        '[class*="promo"]',
        '[class*="beneficio"]',
        '[class*="offer"]',
        '[class*="discount"]',
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

    def _scrape_promotions(self) -> List[PromotionModel]:
        page = self._ensure_page()
        self._navigate(self.BENEFITS_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        self._save_debug_screenshot("itau_main")

        return self._extract_from_page()

    def _extract_from_page(self) -> List[PromotionModel]:
        page = self._ensure_page()
        promotions: List[PromotionModel] = []

        selector = ", ".join(self.CARD_SELECTORS)
        cards = page.locator(selector).all()

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
            body_text = page.locator("body").inner_text()
            promotions = self._extract_from_text(body_text)

        return self._dedupe_promotions(promotions)

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
            r"hasta\s+\d+",
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

    def _build_promo(self, title: str, detail: str) -> Optional[PromotionModel]:
        full_text = f"{title}. {detail}"

        discount_percent: Optional[Decimal] = None
        installment_count: Optional[int] = None
        valid_days: List[str] = []
        valid_from: Optional[datetime.date] = None
        valid_to: Optional[datetime.date] = None
        benefit_type: Optional[str] = None
        category = self._infer_category(title, detail)
        merchant_name = self._infer_merchant(title)

        pct_match = re.search(r"(\d{1,2})\s*%", full_text, re.I)
        if pct_match:
            discount_percent = Decimal(pct_match.group(1))
            if "reintegro" in full_text.lower():
                benefit_type = "reintegro"
            elif "descuento" in full_text.lower():
                benefit_type = "descuento"

        cuotas_match = re.search(r"(\d{1,2})\s*cuotas?", full_text, re.I)
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
            if day_key in full_text.lower():
                valid_days.append(day_norm)

        dates = self._parse_dates(full_text)
        if dates:
            valid_from, valid_to = dates

        if not any([discount_percent, installment_count, valid_days, valid_from, valid_to, category]):
            return None

        return PromotionModel(
            bank_id=self._get_bank_id(),
            title=title,
            merchant_name=merchant_name,
            category=category,
            benefit_type=benefit_type,
            discount_percent=discount_percent,
            installment_count=installment_count,
            valid_days=sorted(list(set(valid_days))),
            valid_from=valid_from,
            valid_to=valid_to,
            source_url=self.BENEFITS_URL,
            raw_text=full_text,
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

    def _infer_merchant(self, title: str) -> Optional[str]:
        generic = {"beneficio", "promoción", "descuento", "oferta", "exclusivo"}
        title_lower = title.lower()
        if title_lower in generic or len(title) < 4:
            return None
        return title

    def _infer_category(self, title: str, detail: str) -> Optional[str]:
        txt = f"{title} {detail}".lower()

        rules = [
            (["supermercado", "carrito", "stock"], "Supermercados"),
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