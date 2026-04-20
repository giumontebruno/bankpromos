import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers.py.py_sudameris import SudamerisPromotionsScraper


class TestSudamerisScraper:
    def test_scraper_returns_list(self, sudameris_html, patch_playwright):
        mp = patch_playwright(sudameris_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            assert isinstance(result, list)

    def test_scraper_returns_promotions(self, sudameris_html, patch_playwright):
        mp = patch_playwright(sudameris_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            assert len(result) > 0
            promo = result[0]
            assert promo.bank_id == "py_sudameris"
            assert promo.title

    def test_has_benefit_signal(self, sudameris_html):
        scraper = SudamerisPromotionsScraper()

        text_with_signal = "20% de descuento en Restaurant Gourmet"
        assert scraper._has_benefit_signal(text_with_signal) is True

        text_without = "Bienvenido a nuestro sitio"
        assert scraper._has_benefit_signal(text_without) is False

    def test_discount_detection(self, patch_playwright):
        html = "<html><body>30% de reintegro en Supermercado Stock</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.discount_percent is not None
                assert int(promo.discount_percent) == 30

    def test_cuotas_detection(self, patch_playwright):
        html = "<html><body>Hasta 6 cuotas sin interes en Tecnologia</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.installment_count is not None

    def test_valid_days_detection(self, patch_playwright):
        html = "<html><body>15% los viernes en Farmacia</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert "viernes" in promo.valid_days

    def test_dedup_removes_duplicates(self, patch_playwright):
        html = "<html><body>20% Restaurant\n20% Restaurant\n25% Restaurant</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = SudamerisPromotionsScraper()
            result = scraper.scrape()

            titles = [p.title for p in result]
            assert len(titles) == len(set(titles))

    def test_category_inference(self):
        scraper = SudamerisPromotionsScraper()

        cat = scraper._infer_category("20% en Supermercado", "descuento")
        assert cat == "Supermercados"

        cat = scraper._infer_category("10% en Restaurant", "bar")
        assert cat == "Gastronomía"

        cat = scraper._infer_category("5% en Universidad", "curso")
        assert cat == "Educación"