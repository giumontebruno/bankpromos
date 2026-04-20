import pytest
from decimal import Decimal

from bankpromos.core.models import FuelPriceModel
from bankpromos.fuel_prices import (
    normalize_fuel_type,
    normalize_emblem,
    get_fuel_prices,
    find_price,
    FUEL_PRICES_STATIC,
)


class TestFuelNormalization:
    def test_normalize_fuel_type_nafta_95(self):
        assert normalize_fuel_type("nafta 95") == "nafta_95"
        assert normalize_fuel_type("95") == "nafta_95"
        assert normalize_fuel_type("premium") == "nafta_95"

    def test_normalize_fuel_type_nafta_93(self):
        assert normalize_fuel_type("93") == "nafta_93"
        assert normalize_fuel_type("regular") == "nafta_93"
        assert normalize_fuel_type("super") == "nafta_93"

    def test_normalize_fuel_type_diesel(self):
        assert normalize_fuel_type("diesel") == "diesel"
        assert normalize_fuel_type("gas oil") == "diesel"

    def test_normalize_fuel_type_nafta_97(self):
        assert normalize_fuel_type("97") == "nafta_97"
        assert normalize_fuel_type("98") == "nafta_97"

    def test_normalize_emblem_shell(self):
        assert normalize_emblem("shell") == "shell"
        assert normalize_emblem("shell Paraguay") == "shell"
        assert normalize_emblem("SHELL") == "shell"

    def test_normalize_emblem_copetrol(self):
        assert normalize_emblem("copetrol") == "copetrol"
        assert normalize_emblem("Copetrol") == "copetrol"

    def test_normalize_emblem_petropar(self):
        assert normalize_emblem("petropar") == "petropar"
        assert normalize_emblem("Petropar") == "petropar"

    def test_normalize_emblem_invalid(self):
        assert normalize_emblem("invalid_placeholder") is None
        assert normalize_emblem("") is None


class TestFuelPrices:
    def test_get_fuel_prices_returns_list(self):
        prices = get_fuel_prices()
        assert isinstance(prices, list)
        assert len(prices) > 0

    def test_get_fuel_prices_has_required_emblems(self):
        prices = get_fuel_prices()
        emblems = set(p.emblem for p in prices)
        assert "shell" in emblems
        assert "copetrol" in emblems

    def test_static_prices_structure(self):
        assert "shell" in FUEL_PRICES_STATIC
        assert "nafta_95" in FUEL_PRICES_STATIC["shell"]

    def test_find_price_exact_match(self):
        prices = get_fuel_prices()
        fp = find_price(prices, "nafta_95", "shell")
        assert fp is not None
        assert fp.emblem == "shell"
        assert fp.fuel_type == "nafta_95"

    def test_find_price_no_match(self):
        prices = get_fuel_prices()
        fp = find_price(prices, "nafta_95", "nonexistent")
        assert fp is None


class TestFuelPriceModel:
    def test_model_creation(self):
        fp = FuelPriceModel(
            emblem="shell",
            fuel_type="nafta_95",
            price=Decimal("9400"),
            source_url="test",
        )
        assert fp.emblem == "shell"
        assert fp.fuel_type == "nafta_95"
        assert fp.price == Decimal("9400")

    def test_model_optional_fields(self):
        fp = FuelPriceModel(
            emblem="copetrol",
            fuel_type="diesel",
            price=Decimal("8000"),
            source_url="test",
        )
        assert fp.updated_at is None
        assert fp.raw_data == {}


class TestFuelTypes:
    def test_all_fuel_types_available(self):
        prices = get_fuel_prices()
        fuel_types = set(p.fuel_type for p in prices)
        assert "nafta_93" in fuel_types
        assert "nafta_95" in fuel_types
        assert "nafta_97" in fuel_types
        assert "diesel" in fuel_types