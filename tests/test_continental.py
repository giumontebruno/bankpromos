import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers.py.py_continental import ContinentalPromotionsScraper


class TestContinentalScraper:
    def test_scraper_returns_list(self, continental_html, patch_playwright):
        mp = patch_playwright(continental_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ContinentalPromotionsScraper()
            result = scraper.scrape()

            assert isinstance(result, list)

    def test_scraper_returns_promotions(self, continental_html, patch_playwright):
        mp = patch_playwright(continental_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ContinentalPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.bank_id == "py_continental"
                assert promo.title

    def test_has_benefit_signal(self):
        scraper = ContinentalPromotionsScraper()

        assert scraper._has_benefit_signal("20% descuento") is True
        assert scraper._has_benefit_signal("6 cuotas") is True
        assert scraper._has_benefit_signal("menu") is False

    def test_discount_detection(self, patch_playwright):
        html = "<html><body>30% en Combustible</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ContinentalPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.discount_percent == 30

    def test_category_inference(self):
        scraper = ContinentalPromotionsScraper()

        cat = scraper._infer_category("10% Supermercado", "stock")
        assert cat == "Supermercados"

        cat = scraper._infer_category("15% Restaurant", "pizza")
        assert cat == "Gastronomía"

    def test_dedup(self, patch_playwright):
        html = "<html><body>10% A\n20% A</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = ContinentalPromotionsScraper()
            result = scraper.scrape()

            if result:
                keys = [scraper._promo_key(p) for p in result]
                assert len(keys) == len(set(keys))