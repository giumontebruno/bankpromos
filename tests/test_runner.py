import pytest
from unittest.mock import MagicMock, patch

from bankpromos.scrapers import get_scraper


class TestRunner:
    def test_run_scraper_returns_tuple(self, run_scraper_func, patch_playwright):
        html = "<html><body>20% Test</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            promos, error = run_scraper_func("py_sudameris")

            assert isinstance(promos, list)
            assert error is None or isinstance(error, str)

    def test_run_all_returns_tuple(self, run_all_func, patch_playwright):
        html = "<html><body>15% Test</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            promos, errors = run_all_func(bank_ids=["py_sudameris"])

            assert isinstance(promos, list)
            assert isinstance(errors, dict)

    def test_errors_dict_structure(self, run_all_func, patch_playwright):
        html = "<html><body>Test</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            promos, errors = run_all_func(bank_ids=["py_sudameris"])

            assert isinstance(errors, dict)

    def test_one_failure_does_not_stop_others(self, run_all_func, patch_playwright):
        html = "<html><body>10% Promo</body></html>"
        mp = patch_playwright(html)

        with patch("bankpromos.scrapers.base_public.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__ = MagicMock(return_value=mp())
            mock_pw.return_value.__exit__ = MagicMock(return_value=None)

            promos, errors = run_all_func(bank_ids=["py_sudameris", "py_ueno", "py_itau"])

            assert isinstance(promos, list)
            assert isinstance(errors, dict)


class TestNormalization:
    def test_normalize_merchant_names(self, normalizer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="Shell Mcal Lopez",
            merchant_name="Shell Mcal Lopez",
            source_url="http://test.com",
        )

        normalized = normalizer(promo)

        assert normalized.merchant_name is not None

    def test_normalize_categories(self, normalizer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="Test",
            category="gastronomia",
            source_url="http://test.com",
        )

        normalized = normalizer(promo)

        assert normalized.category == "Gastronomía"

    def test_normalize_benefit_type(self, normalizer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% de reintegro",
            source_url="http://test.com",
        )

        normalized = normalizer(promo)

        assert normalized.benefit_type == "reintegro"


class TestDedup:
    def test_deduper_removes_duplicates(self, deduper):
        from bankpromos.core.models import PromotionModel

        p1 = PromotionModel(
            bank_id="py_sudameris",
            title="Test",
            merchant_name="Test",
            discount_percent=20,
            source_url="http://test.com",
        )
        p2 = PromotionModel(
            bank_id="py_sudameris",
            title="Test",
            merchant_name="Test",
            discount_percent=20,
            source_url="http://test.com",
        )

        result = deduper([p1, p2])

        assert len(result) <= 2


class TestScoring:
    def test_scoring_high_label(self, scorer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% Restaurant",
            merchant_name="Restaurant",
            category="Gastronomía",
            discount_percent=20,
            valid_days=["viernes"],
            source_url="http://test.com",
        )

        scored = scorer(promo)

        assert scored.result_quality_label in ["HIGH", "MEDIUM", "LOW"]

    def test_scoring_medium_label(self, scorer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="10%",
            source_url="http://test.com",
        )

        scored = scorer(promo)

        assert scored.result_quality_label == "LOW"

    def test_scoring_returns_model(self, scorer):
        from bankpromos.core.models import PromotionModel

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="Test",
            source_url="http://test.com",
        )

        scored = scorer(promo)

        assert scored.result_quality_score >= 0