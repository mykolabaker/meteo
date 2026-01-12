"""API route definitions."""

from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from meteo_proxy.api.dependencies import CacheDep, WeatherServiceDep
from meteo_proxy.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ReadinessResponse,
    WeatherResponse,
)
from meteo_proxy.services.open_meteo import (
    OpenMeteoAPIError,
    OpenMeteoError,
    OpenMeteoTimeoutError,
)

logger = structlog.get_logger()

# API router for weather endpoints
api_router = APIRouter(prefix="/api/v1", tags=["weather"])

# Health router for health checks
health_router = APIRouter(prefix="/health", tags=["health"])


@api_router.get(
    "/weather",
    response_model=WeatherResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid coordinates"},
        502: {"model": ErrorResponse, "description": "Upstream API error"},
        504: {"model": ErrorResponse, "description": "Upstream timeout"},
    },
)
async def get_weather(
    weather_service: WeatherServiceDep,
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitude")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitude")],
) -> WeatherResponse:
    """Get current weather for coordinates.

    Returns current temperature and wind speed for the specified location.
    Results are cached for 60 seconds.
    """
    try:
        return await weather_service.get_weather(lat, lon)

    except OpenMeteoTimeoutError as e:
        logger.error("Upstream timeout", lat=lat, lon=lon, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="UPSTREAM_TIMEOUT",
                    message="Open-Meteo API request timed out",
                )
            ).model_dump(),
        ) from e

    except OpenMeteoAPIError as e:
        logger.error(
            "Upstream API error",
            lat=lat,
            lon=lon,
            status_code=e.status_code,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="UPSTREAM_ERROR",
                    message=f"Open-Meteo API error: {e}",
                )
            ).model_dump(),
        ) from e

    except OpenMeteoError as e:
        logger.error("Upstream request failed", lat=lat, lon=lon, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="UPSTREAM_ERROR",
                    message=f"Open-Meteo API request failed: {e}",
                )
            ).model_dump(),
        ) from e


@health_router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe - checks if the service is running."""
    return HealthResponse(status="ok")


@health_router.get("/ready", response_model=ReadinessResponse)
async def readiness(cache: CacheDep) -> ReadinessResponse:
    """Readiness probe - checks if the service is ready to accept traffic."""
    cache_status = "ok" if cache.is_healthy() else "unhealthy"

    overall_status = "ok" if cache_status == "ok" else "unhealthy"

    response = ReadinessResponse(
        status=overall_status,
        checks={"cache": cache_status},
    )

    if overall_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )

    return response
