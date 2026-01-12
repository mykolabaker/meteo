"""API route definitions."""

from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

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

# Root router for landing page
root_router = APIRouter(tags=["root"])

# API router for weather endpoints
api_router = APIRouter(prefix="/api/v1", tags=["weather"])

# Health router for health checks
health_router = APIRouter(prefix="/health", tags=["health"])


LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meteo Proxy API</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e8e8e8;
        }
        .container {
            max-width: 600px;
            padding: 2rem;
            text-align: center;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #4facfe, #00f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .tagline {
            color: #888;
            margin-bottom: 2rem;
        }
        .example {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 1rem;
            margin: 1.5rem 0;
            text-align: left;
            font-family: monospace;
            font-size: 0.9rem;
            overflow-x: auto;
        }
        .example code { color: #00f2fe; }
        .links {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 2rem;
        }
        .links a {
            color: #4facfe;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border: 1px solid #4facfe;
            border-radius: 4px;
            transition: all 0.2s;
        }
        .links a:hover {
            background: #4facfe;
            color: #1a1a2e;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Meteo Proxy API</h1>
        <p class="tagline">Weather data proxy for Open-Meteo</p>

        <div class="example">
            <code>GET /api/v1/weather?lat=52.52&lon=13.41</code>
        </div>

        <p>Returns current temperature and wind speed for any location.</p>

        <div class="links">
            <a href="/docs">API Docs</a>
            <a href="/api/v1/weather?lat=52.52&lon=13.41">Try It</a>
            <a href="https://github.com/mykolabaker/meteo">GitHub</a>
        </div>
    </div>
</body>
</html>
"""


@root_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page() -> str:
    """Landing page with API information."""
    return LANDING_PAGE_HTML


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
