"""Cache service for weather data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cachetools import TTLCache
from prometheus_client import Counter, Gauge

from meteo_proxy.config import Settings

if TYPE_CHECKING:
    from meteo_proxy.api.schemas import WeatherResponse

# Metrics
cache_hits = Counter("cache_hits_total", "Total cache hits")
cache_misses = Counter("cache_misses_total", "Total cache misses")
cache_size_gauge = Gauge("cache_size", "Current number of cache entries")


class CacheService:
    """TTL-based cache for weather data."""

    def __init__(self, settings: Settings) -> None:
        """Initialize cache with settings."""
        self._cache: TTLCache[str, WeatherResponse] = TTLCache(
            maxsize=settings.cache_max_size,
            ttl=settings.cache_ttl_seconds,
        )
        self._settings = settings

    def _make_key(self, lat: float, lon: float) -> str:
        """Create cache key from coordinates.

        Rounds coordinates to 2 decimal places for better hit rate.
        """
        lat_rounded = round(lat, 2)
        lon_rounded = round(lon, 2)
        return f"weather:{lat_rounded}:{lon_rounded}"

    def get(self, lat: float, lon: float) -> WeatherResponse | None:
        """Get cached weather data for coordinates."""
        key = self._make_key(lat, lon)
        value: WeatherResponse | None = self._cache.get(key)
        if value is not None:
            cache_hits.inc()
            return value
        cache_misses.inc()
        return None

    def set(self, lat: float, lon: float, value: WeatherResponse) -> None:
        """Cache weather data for coordinates."""
        key = self._make_key(lat, lon)
        self._cache[key] = value
        cache_size_gauge.set(len(self._cache))

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        cache_size_gauge.set(0)

    @property
    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)

    def is_healthy(self) -> bool:
        """Check if cache is operational."""
        # Verify the cache object is accessible and functional
        # No side effects - just check the cache exists and can report its size
        return self._cache is not None and isinstance(len(self._cache), int)
