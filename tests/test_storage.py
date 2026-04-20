import os
import pytest
import tempfile
from decimal import Decimal

from bankpromos.core.models import FuelPriceModel, PromotionModel
from bankpromos import storage


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except Exception:
        pass


class TestInitDB:
    def test_init_creates_database(self, temp_db):
        storage.init_db(temp_db)
        assert os.path.exists(temp_db)

    def test_init_creates_tables(self, temp_db):
        storage.init_db(temp_db)
        conn = storage._get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert "promotions" in tables
        assert "fuel_prices" in tables
        assert "metadata" in tables


class TestPromotions:
    def test_save_and_load_promotions(self, temp_db):
        storage.init_db(temp_db)

        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="20% Restaurant",
                merchant_name="Restaurant",
                category="Gastronomia",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)

        loaded = storage.load_promotions(temp_db)

        assert len(loaded) == 1
        assert loaded[0].bank_id == "py_sudameris"
        assert loaded[0].discount_percent == Decimal("20")

    def test_load_empty_database(self, temp_db):
        storage.init_db(temp_db)
        loaded = storage.load_promotions(temp_db)
        assert loaded == []

    def test_save_empty_list(self, temp_db):
        storage.init_db(temp_db)
        storage.save_promotions([], temp_db)
        loaded = storage.load_promotions(temp_db)
        assert loaded == []

    def test_clear_promotions(self, temp_db):
        storage.init_db(temp_db)

        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)
        storage.clear_promotions(temp_db)

        loaded = storage.load_promotions(temp_db)
        assert loaded == []


class TestFuelPrices:
    def test_save_and_load_fuel_prices(self, temp_db):
        storage.init_db(temp_db)

        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)

        loaded = storage.load_fuel_prices(temp_db)

        assert len(loaded) == 1
        assert loaded[0].emblem == "shell"
        assert loaded[0].fuel_type == "nafta_95"

    def test_load_empty_fuel(self, temp_db):
        storage.init_db(temp_db)
        loaded = storage.load_fuel_prices(temp_db)
        assert loaded == []

    def test_clear_fuel_prices(self, temp_db):
        storage.init_db(temp_db)

        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)
        storage.clear_fuel_prices(temp_db)

        loaded = storage.load_fuel_prices(temp_db)
        assert loaded == []


class TestTimestamps:
    def test_promotion_timestamp_set(self, temp_db):
        storage.init_db(temp_db)

        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="Test",
                source_url="http://test.com",
            )
        ]

        storage.save_promotions(promos, temp_db)
        last_update = storage.get_last_promotion_update(temp_db)

        assert last_update is not None

    def test_fuel_timestamp_set(self, temp_db):
        storage.init_db(temp_db)

        prices = [
            FuelPriceModel(
                emblem="shell",
                fuel_type="nafta_95",
                price=Decimal("9400"),
                source_url="static",
            )
        ]

        storage.save_fuel_prices(prices, temp_db)
        last_update = storage.get_last_fuel_update(temp_db)

        assert last_update is not None

    def test_no_timestamp_when_empty(self, temp_db):
        storage.init_db(temp_db)
        last_update = storage.get_last_promotion_update(temp_db)
        assert last_update is None


class TestDataIntegrity:
    def test_promotion_with_all_fields(self, temp_db):
        from datetime import date, datetime

        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% Test",
            merchant_name="Test Merchant",
            category="Test",
            benefit_type="descuento",
            discount_percent=Decimal("20"),
            installment_count=6,
            valid_days=["viernes", "sabado"],
            valid_from=date(2026, 4, 1),
            valid_to=date(2026, 4, 30),
            source_url="http://test.com",
            raw_text="raw",
            raw_data={"key": "value"},
            scraped_at=datetime.now(),
            result_quality_score=5.0,
            result_quality_label="HIGH",
        )

        storage.init_db(temp_db)
        storage.save_promotions([promo], temp_db)

        loaded = storage.load_promotions(temp_db)

        assert loaded[0].title == "20% Test"
        assert loaded[0].merchant_name == "Test Merchant"
        assert loaded[0].discount_percent == Decimal("20")
        assert loaded[0].installment_count == 6
        assert loaded[0].valid_days == ["viernes", "sabado"]