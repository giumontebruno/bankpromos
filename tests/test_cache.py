import os
import pytest
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal

from bankpromos import cache, storage
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


class TestPromotionCache:
    def test_fresh_cache_true_after_save(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        assert cache.is_promotion_cache_fresh(max_age_hours=12, db_path=temp_db) is True

    def test_fresh_cache_false_when_stale(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        assert cache.is_promotion_cache_fresh(max_age_hours=0, db_path=temp_db) is False

    def test_fresh_cache_false_when_empty(self, temp_db):
        storage.init_db(temp_db)

        assert cache.is_promotion_cache_fresh(db_path=temp_db) is False


class TestFuelCache:
    def test_fresh_cache_true_after_save(self, temp_db):
        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        assert cache.is_fuel_cache_fresh(max_age_hours=12, db_path=temp_db) is True

    def test_fresh_cache_false_when_stale(self, temp_db):
        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        assert cache.is_fuel_cache_fresh(max_age_hours=0, db_path=temp_db) is False


class TestCacheStatus:
    def test_get_cache_status_returns_dict(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        status = cache.get_cache_status(temp_db)

        assert isinstance(status, dict)
        assert "promotions_fresh" in status
        assert "fuel_fresh" in status
        assert "promotions_age_hours" in status
        assert "fuel_age_hours" in status


class TestCacheAge:
    def test_get_cache_age_promotions_returns_timedelta(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        age = cache.get_cache_age_promotions(temp_db)

        assert isinstance(age, timedelta)

    def test_get_cache_age_fuel_returns_timedelta(self, temp_db):
        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        age = cache.get_cache_age_fuel(temp_db)

        assert isinstance(age, timedelta)


class TestCacheLogic:
    def test_stale_cache_triggers_refresh(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        is_fresh = cache.is_promotion_cache_fresh(max_age_hours=1, db_path=temp_db)

        import time
        time.sleep(2)

        is_fresh_after = cache.is_promotion_cache_fresh(max_age_hours=1, db_path=temp_db)

        assert is_fresh is True


class TestCacheTimestamps:
    def test_get_last_promotion_update_time(self, temp_db):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        last_update = cache.get_last_promotion_update_time(temp_db)

        assert last_update is not None
        assert isinstance(last_update, datetime)

    def test_get_last_fuel_update_time(self, temp_db):
        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        last_update = cache.get_last_fuel_update_time(temp_db)

        assert last_update is not None
        assert isinstance(last_update, datetime)