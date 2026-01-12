"""Tests for API endpoints."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from meteo_proxy.api.dependencies import reset_singletons
from meteo_proxy.config import get_settings


class TestWeatherEndpoint:
    """Tests for /api/v1/weather endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Reset state before each test."""
        reset_singletons()
        get_settings.cache_clear()

    def test_get_weather_success(self, client: TestClient) -> None:
        """Test successful weather request."""
        settings = get_settings()
        mock_response = {
            "latitude": 52.52,
            "longitude": 13.41,
            "current": {
                "temperature_2m": 15.5,
                "wind_speed_10m": 12.3,
            },
        }

        with respx.mock:
            respx.get(settings.upstream_url).mock(
                return_value=Response(200, json=mock_response)
            )

            response = client.get("/api/v1/weather?lat=52.52&lon=13.41")

            assert response.status_code == 200
            data = response.json()
            assert data["location"]["lat"] == 52.52
            assert data["location"]["lon"] == 13.41
            assert data["current"]["temperatureC"] == 15.5
            assert data["current"]["windSpeedKmh"] == 12.3
            assert data["source"] == "open-meteo"
            assert "retrievedAt" in data

    def test_get_weather_invalid_latitude(self, client: TestClient) -> None:
        """Test invalid latitude returns 422."""
        response = client.get("/api/v1/weather?lat=91&lon=13.41")
        assert response.status_code == 422

    def test_get_weather_invalid_longitude(self, client: TestClient) -> None:
        """Test invalid longitude returns 422."""
        response = client.get("/api/v1/weather?lat=52.52&lon=181")
        assert response.status_code == 422

    def test_get_weather_missing_params(self, client: TestClient) -> None:
        """Test missing parameters returns 422."""
        response = client.get("/api/v1/weather")
        assert response.status_code == 422

    def test_get_weather_cache_hit(self, client: TestClient) -> None:
        """Test cache hit on second request."""
        settings = get_settings()
        mock_response = {
            "latitude": 52.52,
            "longitude": 13.41,
            "current": {
                "temperature_2m": 15.5,
                "wind_speed_10m": 12.3,
            },
        }

        with respx.mock:
            route = respx.get(settings.upstream_url).mock(
                return_value=Response(200, json=mock_response)
            )

            # First request
            response1 = client.get("/api/v1/weather?lat=52.52&lon=13.41")
            assert response1.status_code == 200

            # Second request should use cache
            response2 = client.get("/api/v1/weather?lat=52.52&lon=13.41")
            assert response2.status_code == 200

            # Upstream should only be called once
            assert route.call_count == 1

    def test_get_weather_upstream_timeout(self, client: TestClient) -> None:
        """Test upstream timeout returns 504."""
        settings = get_settings()

        with respx.mock:
            respx.get(settings.upstream_url).mock(
                side_effect=httpx.TimeoutException("timeout")
            )

            response = client.get("/api/v1/weather?lat=52.52&lon=13.41")

            assert response.status_code == 504
            data = response.json()
            assert data["detail"]["error"]["code"] == "UPSTREAM_TIMEOUT"

    def test_get_weather_upstream_error(self, client: TestClient) -> None:
        """Test upstream error returns 502."""
        settings = get_settings()

        with respx.mock:
            respx.get(settings.upstream_url).mock(
                return_value=Response(500, text="Internal Server Error")
            )

            response = client.get("/api/v1/weather?lat=52.52&lon=13.41")

            assert response.status_code == 502
            data = response.json()
            assert data["detail"]["error"]["code"] == "UPSTREAM_ERROR"


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_liveness(self, client: TestClient) -> None:
        """Test liveness probe."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness(self, client: TestClient) -> None:
        """Test readiness probe."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["cache"] == "ok"


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    def test_metrics(self, client: TestClient) -> None:
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Check some expected metrics are present
        assert "http_requests_total" in content or "python_info" in content


class TestOpenAPIEndpoints:
    """Tests for OpenAPI documentation endpoints."""

    def test_docs(self, client: TestClient) -> None:
        """Test Swagger docs endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc(self, client: TestClient) -> None:
        """Test ReDoc endpoint."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json(self, client: TestClient) -> None:
        """Test OpenAPI JSON schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Meteo Proxy API"
