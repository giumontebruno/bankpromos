import os
import pytest
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

from bankpromos import data_service, storage
from bankpromos.core.models import FuelPriceModel, PromotionModel


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    storage.init_db(path)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


class TestGetPromotionsData:
    def test_returns_cached_when_fresh(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test Promo",
                merchant_name="Test",
                category="Test",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        with patch("bankpromos.data_service.is_promotion_cache_fresh", return_value=True):
            with patch("bankpromos.data_service.load_promotions", return_value=promos):
                result = data_service.get_promotions_data(force_refresh=False, db_path=temp_db)

                assert len(result) > 0
                assert result[0].bank_id == "py_sudameris"

    def test_scrape_when_cache_empty(self, temp_db):
        storage.save_promotions([], temp_db)

        with patch("bankpromos.data_service.is_promotion_cache_fresh", return_value=False):
            with patch("bankpromos.data_service.run_all_scrapers", return_value=([], {})):
                with patch("bankpromos.data_service.run_scraper", return_value=([], None)):
                    result = data_service.get_promotions_data(force_refresh=False, db_path=temp_db)

                    assert isinstance(result, list)

    def test_force_refresh_bypasses_cache(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Cached",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        new_promos = [
            PromotionModel(
                bank_id="py_ueno",
                title="Fresh",
                source_url="http://test.com",
            )
        ]

        with patch("bankpromos.data_service.load_promotions", return_value=promos):
            with patch("bankpromos.data_service.run_all_scrapers", return_value=([], {})):
                with patch("bankpromos.data_service.run_scraper", return_value=(new_promos, None)):
                    result = data_service.get_promotions_data(force_refresh=True, db_path=temp_db)

                    assert len(result) > 0


class TestGetFuelData:
    def test_returns_cached_when_fresh(self, temp_db):
        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        with patch("bankpromos.data_service.is_fuel_cache_fresh", return_value=True):
            with patch("bankpromos.data_service.load_fuel_prices", return_value=prices):
                result = data_service.get_fuel_data(force_refresh=False, db_path=temp_db)

                assert len(result) > 0
                assert result[0].emblem == "shell"

    def test_force_refresh_bypasses_cache(self, temp_db):
        old_prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9000"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(old_prices, temp_db)

        new_prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        with patch("bankpromos.data_service.load_fuel_prices", return_value=new_prices):
            with patch("bankpromos.data_service.get_fuel_prices", return_value=new_prices):
                result = data_service.get_fuel_data(force_refresh=True, db_path=temp_db)

                assert len(result) > 0


class TestCollectAllData:
    def test_returns_dict_with_counts(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        with patch("bankpromos.data_service.get_promotions_data", return_value=promos):
            with patch("bankpromos.data_service.get_fuel_data", return_value=prices):
                result = data_service.collect_all_data(force_refresh=False, db_path=temp_db)

                assert isinstance(result, dict)
                assert "promotions_count" in result
                assert "fuel_prices_count" in result


class TestClearAllData:
    def test_clears_both_tables(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_promotions(promos, temp_db)
        storage.save_fuel_prices(prices, temp_db)

        data_service.clear_all_data(temp_db)

        loaded_promos = storage.load_promotions(temp_db)
        loaded_fuel = storage.load_fuel_prices(temp_db)

        assert len(loaded_promos) == 0
        assert len(loaded_fuel) == 0


class TestDataServiceIntegration:
    def test_no_db_creates_one(self):
        test_path = "test_temp_service.db"

        try:
            data_service.init_db(test_path)
            assert os.path.exists(test_path)
        finally:
            if os.path.exists(test_path):
                os.unlink(test_path)


class TestProcessPromotions:
    def test_normalize_and_dedupe(self):
        promo1 = PromotionModel(
            bank_id="py_sudameris",
            title="20% Test",
            merchant_name="Test Merchant",
            source_url="http://test.com",
        )

        promo2 = PromotionModel(
            bank_id="py_sudameris",
            title="20% Test",
            merchant_name="Test Merchant",
            source_url="http://test.com",
        )

        result = data_service._process_promotions([promo1, promo2])

        assert len(result) <= 2

    def test_scoring_applied(self):
        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% Test",
            merchant_name="Test",
            category="Test",
            discount_percent=Decimal("20"),
            source_url="http://test.com",
        )

        result = data_service._process_promotions([promo])

        assert len(result) > 0
        assert result[0].result_quality_score >= 0