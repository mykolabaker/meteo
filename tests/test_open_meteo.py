"""Tests for Open-Meteo client."""

import pytest
import respx
from httpx import Response

from meteo_proxy.config import Settings
from meteo_proxy.services.open_meteo import (
    OpenMeteoAPIError,
    OpenMeteoClient,
    OpenMeteoError,
    OpenMeteoTimeoutError,
)


class TestOpenMeteoClient:
    """Tests for OpenMeteoClient."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_current_weather_success(self) -> None:
        """Test successful weather fetch."""
        settings = Settings()
        client = OpenMeteoClient(settings)

        mock_response = {
            "latitude": 52.52,
            "longitude": 13.41,
            "current": {
                "temperature_2m": 15.5,
                "wind_speed_10m": 12.3,
            },
        }

        respx.get(settings.upstream_url).mock(
            return_value=Response(200, json=mock_response)
        )

        result = await client.get_current_weather(52.52, 13.41)

        assert result.latitude == 52.52
        assert result.longitude == 13.41
        assert result.temperature_c == 15.5
        assert result.wind_speed_kmh == 12.3

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_current_weather_timeout(self) -> None:
        """Test timeout handling."""
        settings = Settings(upstream_timeout_seconds=0.1)
        client = OpenMeteoClient(settings)

        import httpx

        respx.get(settings.upstream_url).mock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(OpenMeteoTimeoutError):
            await client.get_current_weather(52.52, 13.41)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_current_weather_api_error(self) -> None:
        """Test API error handling."""
        settings = Settings()
        client = OpenMeteoClient(settings)

        respx.get(settings.upstream_url).mock(
            return_value=Response(500, text="Internal Server Error")
        )

        with pytest.raises(OpenMeteoAPIError) as exc_info:
            await client.get_current_weather(52.52, 13.41)

        assert exc_info.value.status_code == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_current_weather_400_error(self) -> None:
        """Test 400 error handling."""
        settings = Settings()
        client = OpenMeteoClient(settings)

        respx.get(settings.upstream_url).mock(
            return_value=Response(400, json={"reason": "Invalid coordinates"})
        )

        with pytest.raises(OpenMeteoAPIError) as exc_info:
            await client.get_current_weather(999, 999)

        assert exc_info.value.status_code == 400

    @respx.mock
    @pytest.mark.asyncio
    async def test_parse_response_missing_current_fields_raises_error(self) -> None:
        """Test parsing response with missing weather fields raises error."""
        settings = Settings()
        client = OpenMeteoClient(settings)

        # Response missing temperature and wind data
        mock_response = {
            "latitude": 52.52,
            "longitude": 13.41,
            "current": {},
        }

        respx.get(settings.upstream_url).mock(
            return_value=Response(200, json=mock_response)
        )

        with pytest.raises(OpenMeteoError, match="Missing required weather data"):
            await client.get_current_weather(52.52, 13.41)

    @respx.mock
    @pytest.mark.asyncio
    async def test_parse_response_missing_current_raises_error(self) -> None:
        """Test parsing response with missing current field raises error."""
        settings = Settings()
        client = OpenMeteoClient(settings)

        # Response missing current entirely
        mock_response = {
            "latitude": 52.52,
            "longitude": 13.41,
        }

        respx.get(settings.upstream_url).mock(
            return_value=Response(200, json=mock_response)
        )

        with pytest.raises(OpenMeteoError, match="Missing 'current' field"):
            await client.get_current_weather(52.52, 13.41)
