"""API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Geographic location."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class CurrentWeather(BaseModel):
    """Current weather conditions."""

    temperatureC: float = Field(..., description="Temperature in Celsius")  # noqa: N815
    windSpeedKmh: float = Field(..., description="Wind speed in km/h")  # noqa: N815


class WeatherResponse(BaseModel):
    """Weather API response."""

    location: Location
    current: CurrentWeather
    source: str = Field(default="open-meteo", description="Data source")
    retrievedAt: datetime = Field(..., description="Timestamp of data retrieval")  # noqa: N815


class ErrorDetail(BaseModel):
    """Error detail."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class ErrorResponse(BaseModel):
    """Error response."""

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: str = Field(..., description="Readiness status")
    checks: dict[str, str] = Field(default_factory=dict, description="Component checks")
