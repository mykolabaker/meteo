"""Application configuration management."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Server settings
    app_host: str = Field(default="0.0.0.0", description="Server bind host")
    app_port: int = Field(default=8080, description="Server bind port")

    # Upstream API settings
    upstream_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        description="Open-Meteo API base URL",
    )
    upstream_timeout_seconds: float = Field(
        default=1.0,
        description="Upstream request timeout in seconds",
        ge=0.1,
        le=30.0,
    )

    # Cache settings
    cache_ttl_seconds: int = Field(
        default=60,
        description="Cache TTL in seconds",
        ge=1,
        le=3600,
    )
    cache_max_size: int = Field(
        default=10000,
        description="Maximum cache entries",
        ge=1,
        le=1000000,
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
