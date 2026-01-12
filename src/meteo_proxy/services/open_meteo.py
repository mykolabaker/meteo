"""Open-Meteo API client."""

from dataclasses import dataclass
from typing import Any

import httpx
from prometheus_client import Counter, Histogram

from meteo_proxy.config import Settings


class OpenMeteoError(Exception):
    """Base exception for Open-Meteo client errors."""


class OpenMeteoTimeoutError(OpenMeteoError):
    """Raised when upstream request times out."""


class OpenMeteoAPIError(OpenMeteoError):
    """Raised when upstream returns an error."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


# Metrics
upstream_requests = Counter(
    "upstream_requests_total",
    "Total upstream API requests",
    ["status"],
)
upstream_duration = Histogram(
    "upstream_request_duration_seconds",
    "Upstream request duration in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5],
)


@dataclass
class OpenMeteoResponse:
    """Parsed response from Open-Meteo API."""

    latitude: float
    longitude: float
    temperature_c: float
    wind_speed_kmh: float


class OpenMeteoClient:
    """HTTP client for Open-Meteo Forecast API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize client with settings."""
        self._base_url = settings.upstream_url
        self._timeout = settings.upstream_timeout_seconds

    async def get_current_weather(self, lat: float, lon: float) -> OpenMeteoResponse:
        """Fetch current weather data for coordinates.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)

        Returns:
            Parsed weather data

        Raises:
            OpenMeteoTimeoutError: If request times out
            OpenMeteoAPIError: If upstream returns an error
        """
        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,wind_speed_10m",
        }

        with upstream_duration.time():
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(self._base_url, params=params)

                if response.status_code != 200:
                    upstream_requests.labels(status="error").inc()
                    raise OpenMeteoAPIError(
                        f"Open-Meteo API returned {response.status_code}: {response.text}",
                        response.status_code,
                    )

                upstream_requests.labels(status="success").inc()
                return self._parse_response(response.json())

            except httpx.TimeoutException as e:
                upstream_requests.labels(status="timeout").inc()
                raise OpenMeteoTimeoutError(
                    f"Open-Meteo API request timed out after {self._timeout}s"
                ) from e

            except httpx.RequestError as e:
                upstream_requests.labels(status="error").inc()
                raise OpenMeteoError(f"Open-Meteo API request failed: {e}") from e

    def _parse_response(self, data: dict[str, Any]) -> OpenMeteoResponse:
        """Parse Open-Meteo API response.

        Raises:
            OpenMeteoError: If required fields are missing from response
        """
        if "latitude" not in data or "longitude" not in data:
            raise OpenMeteoError("Missing required coordinate fields in response")

        current = data.get("current")
        if current is None:
            raise OpenMeteoError("Missing 'current' field in response")

        if "temperature_2m" not in current or "wind_speed_10m" not in current:
            raise OpenMeteoError("Missing required weather data in 'current' field")

        return OpenMeteoResponse(
            latitude=data["latitude"],
            longitude=data["longitude"],
            temperature_c=current["temperature_2m"],
            wind_speed_kmh=current["wind_speed_10m"],
        )
