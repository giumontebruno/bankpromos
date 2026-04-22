import pytest
from decimal import Decimal
from datetime import datetime

from bankpromos.core.models import PromotionModel
from bankpromos.core.normalizer import (
    _is_valid_merchant_candidate,
    _is_valid_merchant_name,
    normalize_merchant_name,
    normalize_category,
    _contains_fuel_signal,
    _is_weak_promotion,
)
from bankpromos.fuel_query import _is_fuel_promo, _extract_emblem_from_text
from bankpromos.storage import init_db, save_promotions, load_promotions, get_last_promotion_update


class TestMerchantValidation:
    def test_rejects_pure_numbers(self):
        assert not _is_valid_merchant_name("45")
        assert not _is_valid_merchant_name("40")
        assert not _is_valid_merchant_name("30")
        assert not _is_valid_merchant_name("100")
        assert not _is_valid_merchant_name(" 15 ")

    def test_rejects_generic_words(self):
        assert not _is_valid_merchant_name("Obtené")
        assert not _is_valid_merchant_name("obtené")
        assert not _is_valid_merchant_name("Hasta")
        assert not _is_valid_merchant_name("Promociones")
        assert not _is_valid_merchant_name("Beneficios")
        assert not _is_valid_merchant_name("Vigencia")
        assert not _is_valid_merchant_name("Exclusivos")
        assert not _is_valid_merchant_name("Consumo")

    def test_rejects_percentage_fragments(self):
        assert not _is_valid_merchant_name("30%")
        assert not _is_valid_merchant_name("20%")
        assert not _is_valid_merchant_name(" 40% ")
        assert not _is_valid_merchant_name("45 %")

    def test_accepts_valid_merchants(self):
        assert _is_valid_merchant_name("Shell")
        assert _is_valid_merchant_name("Superseis")
        assert _is_valid_merchant_name("Copetrol")
        assert _is_valid_merchant_name("Stock")
        assert _is_valid_merchant_name("Enex")
        assert _is_valid_merchant_name("Restaurante El Pato")

    def test_normalize_merchant_returns_none_for_invalid(self):
        assert normalize_merchant_name("45") is None
        assert normalize_merchant_name("Obtené") is None
        assert normalize_merchant_name("30%") is None
        assert normalize_merchant_name("") is None
        assert normalize_merchant_name(None) is None

    def test_normalize_merchant_returns_valid_merchants(self):
        result = normalize_merchant_name("shell")
        assert result is not None
        assert result.lower() == "shell"


class TestFuelSignals:
    def test_detects_fuel_keywords(self):
        assert _contains_fuel_signal("descuento en combustible")
        assert _contains_fuel_signal("estacion de servicio Shell")
        assert _contains_fuel_signal("reintegro Copetrol")
        assert _contains_fuel_signal("nafta 95 descuento")
        assert _contains_fuel_signal("diesel Petrobras")
        assert _contains_fuel_signal("estacion Enex")

    def test_normalize_category_detects_fuel(self):
        result = normalize_category("Combustible")
        assert result == "Combustible"

        result = normalize_category("Estacion", "descuento en Shell")
        assert result == "Combustible"

        result = normalize_category(None, "reintegro en estacion de servicio")
        assert result == "Combustible"


class TestFuelPromoDetection:
    def test_detects_fuel_by_category(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Combustible",
            merchant_name="Shell",
            category="Combustible",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo)

    def test_detects_fuel_by_merchant(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% de descuento",
            merchant_name="Shell McQueen",
            category="General",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo)

    def test_detects_fuel_by_raw_text(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="Promocion General",
            merchant_name=None,
            category="General",
            raw_text="Descuento en estacion de servicio Copetrol",
            source_url="http://test.com",
        )
        assert _is_fuel_promo(promo)

    def test_rejects_non_fuel_promos(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Supermercado",
            merchant_name="Stock",
            category="Supermercados",
            source_url="http://test.com",
        )
        assert not _is_fuel_promo(promo)


class TestEmblemExtraction:
    def test_extracts_shell(self):
        assert _extract_emblem_from_text("descuento en Shell") == "shell"
        assert _extract_emblem_from_text("Shell Mcal Lopez") == "shell"
        assert _extract_emblem_from_text("estacion shell") == "shell"

    def test_extracts_copetrol(self):
        assert _extract_emblem_from_text("Copetrol") == "copetrol"
        assert _extract_emblem_from_text("estacion Copetrol") == "copetrol"

    def test_extracts_petropar(self):
        assert _extract_emblem_from_text("Petropar") == "petropar"
        assert _extract_emblem_from_text("combustible Petropar") == "petropar"

    def test_extracts_petrobras(self):
        assert _extract_emblem_from_text("Petrobras") == "petrobras"

    def test_extracts_enex(self):
        assert _extract_emblem_from_text("Enex") == "enex"
        assert _extract_emblem_from_text("estacion Enex") == "enex"


class TestWeakPromotionFilter:
    def test_rejects_generic_title_no_merchant(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="Promociones",
            merchant_name=None,
            category="General",
            source_url="http://test.com",
        )
        assert _is_weak_promotion(promo)

    def test_rejects_number_only_title(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="30%",
            merchant_name=None,
            category="General",
            source_url="http://test.com",
        )
        assert _is_weak_promotion(promo)

    def test_accepts_valid_promo_with_merchant(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Shell",
            merchant_name="Shell",
            category="Combustible",
            source_url="http://test.com",
        )
        assert not _is_weak_promotion(promo)

    def test_accepts_fuel_promo_without_explicit_merchant(self):
        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% Combustible",
            merchant_name=None,
            category="Combustible",
            raw_text="estacion de servicio Shell",
            source_url="http://test.com",
        )
        assert not _is_weak_promotion(promo)


class TestCacheTimestamps:
    def test_save_and_load_promotions_with_timestamp(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Shell",
            merchant_name="Shell",
            category="Combustible",
            source_url="http://test.com",
        )

        save_promotions([promo], db_path)

        last_update = get_last_promotion_update(db_path)
        assert last_update is not None
        assert isinstance(last_update, datetime)

        loaded = load_promotions(db_path)
        assert len(loaded) == 1
        assert loaded[0].title == "10% en Shell"

    def test_cache_status_reflects_real_state(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        from bankpromos.cache import get_cache_status

        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Shell",
            merchant_name="Shell",
            category="Combustible",
            source_url="http://test.com",
        )

        save_promotions([promo], db_path)

        status = get_cache_status(db_path)
        assert status["promotions_fresh"] is True
        assert status["promotions_updated_at"] is not None


class TestFuelMatching:
    def test_fuel_query_returns_results_for_fuel_promo(self):
        from bankpromos.fuel_prices import get_fuel_prices
        from bankpromos.fuel_query import find_best_fuel_promotions

        promo = PromotionModel(
            bank_id="py_ueno",
            title="10% en Shell Combustible",
            merchant_name="Shell",
            category="Combustible",
            discount_percent=Decimal("10"),
            valid_days=["lunes", "martes", "miercoles", "jueves", "viernes"],
            source_url="http://test.com",
        )

        fuel_prices = get_fuel_prices()
        matches = find_best_fuel_promotions([promo], fuel_prices, "nafta_95", "shell")

        assert len(matches) > 0
        assert matches[0]["bank_id"] == "py_ueno"
        assert matches[0]["emblem"] == "shell"
        assert matches[0]["fuel_type"] == "nafta_95"
        assert float(matches[0]["base_price"]) > 0

    def test_fuel_query_filters_by_emblem(self):
        from bankpromos.fuel_prices import get_fuel_prices
        from bankpromos.fuel_query import find_best_fuel_promotions

        promo_shell = PromotionModel(
            bank_id="py_ueno",
            title="10% Shell",
            merchant_name="Shell",
            category="Combustible",
            discount_percent=Decimal("10"),
            source_url="http://test.com",
        )
        promo_copetrol = PromotionModel(
            bank_id="py_itau",
            title="10% Copetrol",
            merchant_name="Copetrol",
            category="Combustible",
            discount_percent=Decimal("15"),
            source_url="http://test.com",
        )

        fuel_prices = get_fuel_prices()
        matches = find_best_fuel_promotions([promo_shell, promo_copetrol], fuel_prices, "nafta_95", "shell")

        assert len(matches) > 0
        for m in matches:
            assert m["emblem"] == "shell"

    def test_fuel_query_ranks_by_price(self):
        from bankpromos.fuel_prices import get_fuel_prices
        from bankpromos.fuel_query import find_best_fuel_promotions

        promo_high = PromotionModel(
            bank_id="py_ueno",
            title="5% Shell",
            merchant_name="Shell",
            category="Combustible",
            discount_percent=Decimal("5"),
            source_url="http://test.com",
        )
        promo_low = PromotionModel(
            bank_id="py_itau",
            title="10% Copetrol",
            merchant_name="Copetrol",
            category="Combustible",
            discount_percent=Decimal("10"),
            source_url="http://test.com",
        )

        fuel_prices = get_fuel_prices()
        matches = find_best_fuel_promotions([promo_high, promo_low], fuel_prices, "nafta_95", None)

        assert len(matches) > 0
        assert matches[0]["estimated_final_price"] <= matches[-1]["estimated_final_price"]