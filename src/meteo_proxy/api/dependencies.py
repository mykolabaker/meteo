"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends

from meteo_proxy.config import Settings, get_settings
from meteo_proxy.services.cache import CacheService
from meteo_proxy.services.open_meteo import OpenMeteoClient
from meteo_proxy.services.weather import WeatherService

# Singleton instances for services
_cache_service: CacheService | None = None
_open_meteo_client: OpenMeteoClient | None = None


def get_cache_service(settings: Annotated[Settings, Depends(get_settings)]) -> CacheService:
    """Get cache service instance (singleton)."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(settings)
    return _cache_service


def get_open_meteo_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OpenMeteoClient:
    """Get Open-Meteo client instance (singleton)."""
    global _open_meteo_client
    if _open_meteo_client is None:
        _open_meteo_client = OpenMeteoClient(settings)
    return _open_meteo_client


def get_weather_service(
    cache: Annotated[CacheService, Depends(get_cache_service)],
    client: Annotated[OpenMeteoClient, Depends(get_open_meteo_client)],
) -> WeatherService:
    """Get weather service instance."""
    return WeatherService(cache, client)


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
CacheDep = Annotated[CacheService, Depends(get_cache_service)]
WeatherServiceDep = Annotated[WeatherService, Depends(get_weather_service)]


def reset_singletons() -> None:
    """Reset singleton instances (for testing)."""
    global _cache_service, _open_meteo_client
    _cache_service = None
    _open_meteo_client = None
