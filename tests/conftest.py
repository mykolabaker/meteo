"""Test fixtures."""

import pytest
from fastapi.testclient import TestClient

from meteo_proxy.api.dependencies import reset_singletons
from meteo_proxy.config import Settings, get_settings
from meteo_proxy.main import create_app
from meteo_proxy.services.cache import CacheService
from meteo_proxy.services.open_meteo import OpenMeteoClient


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        upstream_timeout_seconds=1.0,
        cache_ttl_seconds=60,
        cache_max_size=1000,
        log_level="DEBUG",
        log_format="text",
    )


@pytest.fixture
def cache_service(settings: Settings) -> CacheService:
    """Create test cache service."""
    return CacheService(settings)


@pytest.fixture
def open_meteo_client(settings: Settings) -> OpenMeteoClient:
    """Create test Open-Meteo client."""
    return OpenMeteoClient(settings)


@pytest.fixture
def app():
    """Create test application."""
    # Reset singletons before each test
    reset_singletons()
    # Clear settings cache
    get_settings.cache_clear()
    return create_app()


@pytest.fixture
def client(app) -> TestClient:
    """Create test client."""
    return TestClient(app)
