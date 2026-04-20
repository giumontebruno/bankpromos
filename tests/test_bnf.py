import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers.py.py_bnf import BnfPromotionsScraper


class TestBnfScraper:
    def test_scraper_returns_list(self, bnf_html, patch_playwright):
        mp = patch_playwright(bnf_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = BnfPromotionsScraper()
            result = scraper.scrape()

            assert isinstance(result, list)

    def test_scraper_returns_promotions(self, bnf_html, patch_playwright):
        mp = patch_playwright(bnf_html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = BnfPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.bank_id == "py_bnf"
                assert promo.title

    def test_has_benefit_signal(self):
        scraper = BnfPromotionsScraper()

        assert scraper._has_benefit_signal("25% descuento") is True
        assert scraper._has_benefit_signal("12 cuotas") is True
        assert scraper._has_benefit_signal("menu") is False

    def test_discount_detection(self, patch_playwright):
        html = "<html><body>20% en Hogar</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = BnfPromotionsScraper()
            result = scraper.scrape()

            if result:
                promo = result[0]
                assert promo.discount_percent is not None

    def test_pdf_extraction(self, patch_requests):
        mock_req = patch_requests(b"PDF content", "")

        with patch("bankpromos.scrapers.py.py_bnf.requests") as mock_r:
            mock_r.get = mock_req.get

            scraper = BnfPromotionsScraper()
            result = scraper._parse_pdf_promotions("http://test.com/test.pdf")

            assert isinstance(result, list)

    def test_category_inference(self):
        scraper = BnfPromotionsScraper()

        cat = scraper._infer_category("10% Supermercado", "carrito")
        assert cat == "Supermercados"

        cat = scraper._infer_category("15% Viajes", "hotel")
        assert cat == "Viajes"

    def test_dedup(self, patch_playwright):
        html = "<html><body>10% A\n20% A</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            scraper = BnfPromotionsScraper()
            result = scraper.scrape()

            if result:
                keys = [scraper._promo_key(p) for p in result]
                assert len(keys) == len(set(keys))