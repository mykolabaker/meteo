"""Weather service orchestrating cache and upstream client."""

from datetime import UTC, datetime

import structlog

from meteo_proxy.api.schemas import CurrentWeather, Location, WeatherResponse
from meteo_proxy.services.cache import CacheService
from meteo_proxy.services.open_meteo import OpenMeteoClient

logger = structlog.get_logger()


class WeatherService:
    """Service for fetching weather data with caching."""

    def __init__(self, cache: CacheService, client: OpenMeteoClient) -> None:
        """Initialize service with cache and client."""
        self._cache = cache
        self._client = client

    async def get_weather(self, lat: float, lon: float) -> WeatherResponse:
        """Get current weather for coordinates.

        Checks cache first, fetches from upstream on cache miss.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Weather response with current conditions
        """
        # Check cache first
        cached = self._cache.get(lat, lon)
        if cached is not None:
            logger.info(
                "Cache hit for weather request",
                lat=lat,
                lon=lon,
                cache_hit=True,
            )
            return cached

        # Fetch from upstream
        logger.info(
            "Cache miss, fetching from upstream",
            lat=lat,
            lon=lon,
            cache_hit=False,
        )

        upstream_data = await self._client.get_current_weather(lat, lon)

        # Build response
        response = WeatherResponse(
            location=Location(
                lat=upstream_data.latitude,
                lon=upstream_data.longitude,
            ),
            current=CurrentWeather(
                temperatureC=upstream_data.temperature_c,
                windSpeedKmh=upstream_data.wind_speed_kmh,
            ),
            source="open-meteo",
            retrievedAt=datetime.now(UTC),
        )

        # Cache the response
        self._cache.set(lat, lon, response)

        return response
