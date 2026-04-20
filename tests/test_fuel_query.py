import pytest
from decimal import Decimal

from bankpromos.core.models import FuelPriceModel, PromotionModel
from bankpromos.fuel_query import (
    _is_fuel_promo,
    _calculate_final_price,
    _calculate_savings,
    find_best_fuel_promotions,
    parse_fuel_intent,
    get_fuel_results,
)
from bankpromos.fuel_prices import get_fuel_prices


class TestFuelQueryIntents:
    def test_parse_fuel_intent_shell(self):
        result = parse_fuel_intent("mejor tarjeta shell 95")
        assert result["is_fuel_query"] is True
        assert result["fuel_type"] == "nafta_95"
        assert result["emblem"] == "shell"

    def test_parse_fuel_intent_copetrol(self):
        result = parse_fuel_intent("promo copetrol diesel")
        assert result["is_fuel_query"] is True
        assert result["fuel_type"] == "diesel"
        assert result["emblem"] == "copetrol"

    def test_parse_fuel_intent_nafta_only(self):
        result = parse_fuel_intent("mejor nafta 95")
        assert result["is_fuel_query"] is True
        assert result["fuel_type"] == "nafta_95"

    def test_parse_fuel_intent_diesel(self):
        result = parse_fuel_intent("descuento diesel")
        assert result["is_fuel_query"] is True
        assert result["fuel_type"] == "diesel"

    def test_parse_fuel_intent_non_fuel(self):
        result = parse_fuel_intent("supermercados descuento")
        assert result["is_fuel_query"] is False


class TestFuelPromoDetection:
    def test_is_fuel_promo_with_shell(self):
        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% de descuento en Shell",
            merchant_name="Shell",
            category="Combustible",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo) is True

    def test_is_fuel_promo_with_combustible_category(self):
        promo = PromotionModel(
            bank_id="py_sudameris",
            title="10% Estacion de Servicio",
            merchant_name="Shell Lopez",
            category="Combustible",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo) is True

    def test_is_fuel_promo_negative(self):
        promo = PromotionModel(
            bank_id="py_sudameris",
            title="20% Restaurant",
            merchant_name="Restaurant Gourmet",
            category="Gastronomia",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo) is False


class TestPriceCalculation:
    def test_calculate_final_price_with_discount(self):
        base = Decimal("9000")
        discount = Decimal("20")
        final = _calculate_final_price(base, discount)
        assert final == Decimal("7200")

    def test_calculate_final_price_without_discount(self):
        base = Decimal("9000")
        discount = None
        final = _calculate_final_price(base, discount)
        assert final == Decimal("9000")

    def test_calculate_final_price_zero_discount(self):
        base = Decimal("9000")
        discount = Decimal("0")
        final = _calculate_final_price(base, discount)
        assert final == Decimal("9000")

    def test_calculate_savings(self):
        base = Decimal("9000")
        final = Decimal("7200")
        savings = _calculate_savings(base, final)
        assert savings == Decimal("1800")


class TestFindBestFuelPromotions:
    def test_find_best_fuel_promotions_returns_list(self):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="20% en Shell",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
        ]
        fuel_prices = get_fuel_prices()

        results = find_best_fuel_promotions(promos, fuel_prices, "nafta_95", "shell")

        assert isinstance(results, list)

    def test_find_best_fuel_promotions_with_final_price(self):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="20% Shell",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
        ]
        fuel_prices = get_fuel_prices()

        results = find_best_fuel_promotions(promos, fuel_prices, "nafta_95", "shell")

        if results:
            assert "estimated_final_price" in results[0]
            assert float(results[0]["estimated_final_price"]) > 0

    def test_find_best_fuel_promotions_empty_promos(self):
        promos = []
        fuel_prices = get_fuel_prices()

        results = find_best_fuel_promotions(promos, fuel_prices, "nafta_95", "shell")

        assert results == []

    def test_find_best_fuel_promotions_sorted_by_final_price(self):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="10% Shell",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("10"),
                source_url="http://test.com",
            ),
            PromotionModel(
                bank_id="py_ueno",
                title="20% Shell",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            ),
        ]
        fuel_prices = get_fuel_prices()

        results = find_best_fuel_promotions(promos, fuel_prices, "nafta_95", "shell")

        if len(results) > 1:
            assert results[0]["estimated_final_price"] <= results[1]["estimated_final_price"]


class TestGetFuelResults:
    def test_get_fuel_results_returns_list(self):
        promos = [
            PromotionModel(
                bank_id="py_sudameris",
                title="20% en Shell",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
        ]

        results = get_fuel_results(promos, "nafta_95", "shell", limit=5)

        assert isinstance(results, list)

    def test_get_fuel_results_respects_limit(self):
        promos = [
            PromotionModel(
                bank_id=f"py_{i}",
                title=f"20% Shell {i}",
                merchant_name="Shell",
                category="Combustible",
                discount_percent=Decimal("20"),
                source_url="http://test.com",
            )
            for i in range(20)
        ]

        results = get_fuel_results(promos, "nafta_95", "shell", limit=5)

        assert len(results) <= 5


class TestFuelQueryCLIIntegration:
    def test_fuel_intent_from_query(self):
        result = parse_fuel_intent("mejor tarjeta para nafta 95")
        assert result["is_fuel_query"] is True

    def test_fuel_intent_with_emblem(self):
        result = parse_fuel_intent("copetrol 95 hoy")
        assert result["is_fuel_query"] is True
        assert result["emblem"] == "copetrol"

    def test_fuel_intent_with_diesel(self):
        result = parse_fuel_intent("shell diesel")
        assert result["is_fuel_query"] is True
        assert result["fuel_type"] == "diesel"