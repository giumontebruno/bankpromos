import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers.py.py_itau import ItauPromotionsScraper


class TestItauScraper:
    def test_scraper_returns_list(self, itau_html, patch_playwright):
        mp = patch_playwright(itau_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ItauPromotionsScraper()
            result = scraper.scrape()

            assert isinstance(result, list)

    def test_scraper_returns_promotions(self, itau_html, patch_playwright):
        mp = patch_playwright(itau_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ItauPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.bank_id == "py_itau"
                assert promo.title

    def test_has_benefit_signal(self):
        scraper = ItauPromotionsScraper()

        assert scraper._has_benefit_signal("30% descuento") is True
        assert scraper._has_benefit_signal("12 cuotas") is True
        assert scraper._has_benefit_signal("vigencia") is True
        assert scraper._has_benefit_signal("menu") is False

    def test_discount_detection(self, patch_playwright):
        html = "<html><body>25% en Tecnologia</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ItauPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.discount_percent is not None

    def test_category_inference(self):
        scraper = ItauPromotionsScraper()

        cat = scraper._infer_category("10% Supermercado", "carrito")
        assert cat == "Supermercados"

        cat = scraper._infer_category("15% Restaurante", "bar")
        assert cat == "Gastronomía"

        cat = scraper._infer_category("20% Farmacia", "salud")
        assert cat == "Salud"

    def test_dedup(self, patch_playwright):
        html = "<html><body>10% A\n20% A</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ItauPromotionsScraper()
            result = scraper.scrape()

            if result:
                keys = [scraper._promo_key(p) for p in result]
                assert len(keys) == len(set(keys))