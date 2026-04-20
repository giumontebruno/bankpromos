import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid

from fastapi.testclient import TestClient


@pytest.fixture
def mock_api():
    with patch("bankpromos.api.init_db"):
        with patch("bankpromos.api.get_cache_status") as mock_cache:
            with patch("bankpromos.api.list_scrapers") as mock_banks:
                with patch("bankpromos.api.get_promotions_data") as mock_promos:
                    with patch("bankpromos.api.get_fuel_data") as mock_fuel:
                        with patch("bankpromos.api.collect_all_data") as mock_collect:
                            mock_cache.return_value = {
                                "promotions_fresh": True,
                                "fuel_fresh": True,
                                "promotions_age_hours": 1.0,
                                "fuel_age_hours": 2.0,
                                "promotions_updated_at": None,
                                "fuel_updated_at": None,
                            }
                            mock_banks.return_value = [
                                "py_sudameris",
                                "py_ueno",
                                "py_itau",
                                "py_continental",
                                "py_bnf",
                            ]
                            mock_promos.return_value = []
                            mock_fuel.return_value = []
                            mock_collect.return_value = {
                                "promotions_count": 10,
                                "fuel_prices_count": 5,
                                "promos_updated": "2026-04-20T10:00:00",
                                "fuel_updated": "2026-04-20T10:00:00",
                            }

                            from bankpromos import api

                            api.app.title = "Test API"

                            client = TestClient(api.app)
                            yield client


class TestHealthEndpoint:
    def test_health_returns_ok(self, mock_api):
        response = mock_api.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCacheEndpoint:
    def test_cache_endpoint_exists(self, mock_api):
        response = mock_api.get("/cache")
        assert response.status_code == 200

    def test_cache_returns_fresh_status(self, mock_api):
        response = mock_api.get("/cache")
        data = response.json()
        assert "promotions_fresh" in data
        assert "fuel_fresh" in data


class TestBanksEndpoint:
    def test_banks_returns_list(self, mock_api):
        response = mock_api.get("/banks")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_banks_has_bank_id(self, mock_api):
        response = mock_api.get("/banks")
        data = response.json()
        assert data[0]["bank_id"]


class TestCollectEndpoint:
    def test_collect_returns_counts(self, mock_api):
        response = mock_api.post("/collect?force=false")
        assert response.status_code == 200

        data = response.json()
        assert "promotions_count" in data
        assert "fuel_prices_count" in data

    def test_collect_force_param(self, mock_api):
        response = mock_api.post("/collect?force=true")
        assert response.status_code == 200


class TestCollectFuelEndpoint:
    def test_collect_fuel_exists(self, mock_api):
        response = mock_api.post("/collect-fuel")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data


class TestQueryEndpoint:
    def test_query_returns_results(self, mock_api):
        with patch("bankpromos.api.query_promotions") as mock_q:
            mock_q.return_value = []

            response = mock_api.get("/query?q=combustible")
            assert response.status_code == 200

    def test_query_with_limit(self, mock_api):
        with patch("bankpromos.api.query_promotions") as mock_q:
            mock_q.return_value = []

            response = mock_api.get("/query?q=test&limit=5")
            assert response.status_code == 200

        response = mock_api.get("/query?q=test&limit=100")
        assert response.status_code == 422


class TestFuelEndpoint:
    def test_fuel_returns_results(self, mock_api):
        response = mock_api.get("/fuel?q=nafta")
        assert response.status_code == 200

        data = response.json()
        assert "results" in data


class TestFuelPricesEndpoint:
    def test_fuel_prices_returns_list(self, mock_api):
        response = mock_api.get("/fuel-prices")
        assert response.status_code == 200

        data = response.json()
        assert "prices" in data


class TestErrorHandling:
    def test_invalid_query_returns_500(self, mock_api):
        with patch("bankpromos.api.get_promotions_data", side_effect=Exception("Test error")):
            response = mock_api.get("/query?q=test")
            assert response.status_code == 500

    def test_invalid_fuel_query_returns_500(self, mock_api):
        with patch("bankpromos.api.find_best_fuel_promotions", side_effect=Exception("Test error")):
            response = mock_api.get("/fuel?q=test")
            assert response.status_code == 500


class TestResponseSerialization:
    def test_query_response_structure(self, mock_api):
        with patch("bankpromos.api.query_promotions") as mock_q:
            from bankpromos.core.models import PromotionModel
            from decimal import Decimal

            mock_promo = MagicMock()
            mock_promo.bank_id = "py_sudameris"
            mock_promo.title = "20% Test"
            mock_promo.merchant_name = "Test"
            mock_promo.category = "Test"
            mock_promo.benefit_type = "descuento"
            mock_promo.discount_percent = Decimal("20")
            mock_promo.installment_count = None
            mock_promo.valid_days = ["viernes"]
            mock_promo.source_url = "http://test.com"
            mock_promo.result_quality_score = 5.0
            mock_promo.result_quality_label = "HIGH"

            mock_q.return_value = [mock_promo]

            response = mock_api.get("/query?q=test")
            data = response.json()

            assert "results" in data
            assert len(data["results"]) == 1