"""Tests for cache service."""

import time

from meteo_proxy.config import Settings
from meteo_proxy.services.cache import CacheService


class TestCacheService:
    """Tests for CacheService."""

    def test_set_and_get(self, cache_service: CacheService) -> None:
        """Test basic set and get operations."""
        cache_service.set(52.52, 13.41, {"temp": 10.5})
        result = cache_service.get(52.52, 13.41)
        assert result == {"temp": 10.5}

    def test_cache_miss(self, cache_service: CacheService) -> None:
        """Test cache miss returns None."""
        result = cache_service.get(52.52, 13.41)
        assert result is None

    def test_coordinate_rounding(self, cache_service: CacheService) -> None:
        """Test coordinates are rounded for cache key."""
        # 52.5234 rounds to 52.52, 13.4156 rounds to 13.42
        cache_service.set(52.5234, 13.4156, {"temp": 10.5})
        # 52.5244 rounds to 52.52, 13.4199 rounds to 13.42 - should hit
        result = cache_service.get(52.5244, 13.4199)
        assert result == {"temp": 10.5}

    def test_different_coordinates_miss(self, cache_service: CacheService) -> None:
        """Test different coordinates don't hit cache."""
        cache_service.set(52.52, 13.41, {"temp": 10.5})
        result = cache_service.get(51.50, 0.12)
        assert result is None

    def test_clear(self, cache_service: CacheService) -> None:
        """Test clearing cache."""
        cache_service.set(52.52, 13.41, {"temp": 10.5})
        cache_service.clear()
        result = cache_service.get(52.52, 13.41)
        assert result is None

    def test_size(self, cache_service: CacheService) -> None:
        """Test cache size tracking."""
        assert cache_service.size == 0
        cache_service.set(52.52, 13.41, {"temp": 10.5})
        assert cache_service.size == 1
        cache_service.set(51.50, 0.12, {"temp": 5.0})
        assert cache_service.size == 2

    def test_is_healthy(self, cache_service: CacheService) -> None:
        """Test health check."""
        assert cache_service.is_healthy() is True

    def test_ttl_expiration(self) -> None:
        """Test TTL expiration."""
        settings = Settings(cache_ttl_seconds=1, cache_max_size=100)
        cache = CacheService(settings)
        cache.set(52.52, 13.41, {"temp": 10.5})

        # Should be present immediately
        assert cache.get(52.52, 13.41) is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Should be expired now
        assert cache.get(52.52, 13.41) is None

    def test_max_size(self) -> None:
        """Test max size eviction."""
        settings = Settings(cache_ttl_seconds=60, cache_max_size=2)
        cache = CacheService(settings)

        cache.set(1.0, 1.0, {"temp": 1})
        cache.set(2.0, 2.0, {"temp": 2})
        cache.set(3.0, 3.0, {"temp": 3})

        # First entry should be evicted
        assert cache.size == 2
        assert cache.get(1.0, 1.0) is None
        assert cache.get(2.0, 2.0) is not None
        assert cache.get(3.0, 3.0) is not None
