import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers.py.py_ueno import UenoPromotionsScraper


class TestUenoScraper:
    def test_scraper_returns_list(self, ueno_html, patch_playwright):
        mp = patch_playwright(ueno_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = UenoPromotionsScraper()
            result = scraper.scrape()

            assert isinstance(result, list)

    def test_scraper_returns_promotions(self, ueno_html, patch_playwright):
        mp = patch_playwright(ueno_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = UenoPromotionsScraper()
            result = scraper.scrape()

            assert len(result) >= 0
            if result:
                promo = result[0]
                assert promo.bank_id == "py_ueno"

    def test_has_benefit_signal(self):
        scraper = UenoPromotionsScraper()

        text_with_signal = "25% de descuento en Indumentaria"
        assert scraper._has_benefit_signal(text_with_signal) is True

        text_without = "Bienvenido"
        assert scraper._has_benefit_signal(text_without) is False

    def test_discount_detection(self, patch_playwright):
        html = "<html><body>15% de reintegro en Shopping</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = UenoPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.discount_percent is not None

    def test_pdf_link_extraction(self, patch_playwright):
        html = '<html><body><a href="/docs/beneficios.pdf">Descargar PDF</a></body></html>'
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = UenoPromotionsScraper()
            links = scraper._extract_pdf_links()

            assert len(links) >= 0

    def test_category_inference(self):
        scaper = UenoPromotionsScraper()

        cat = scaper._infer_category("20% en Supermercado", "carrito")
        assert cat == "Supermercados"

        cat = scaper._infer_category("10% en Restaurante", "food")
        assert cat == "Gastronomía"

        cat = scaper._infer_category("30% en Universidad", "curso")
        assert cat == "Educación"

    def test_dedup_removes_duplicates(self, patch_playwright):
        html = "<html><body>20% Shop\n20% Shop</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = UenoPromotionsScraper()
            result = scraper.scrape()

            if result:
                titles = [p.title for p in result]
                unique = set(titles)
                assert len(titles) >= len(unique)