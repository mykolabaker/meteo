"""Application entry point."""

import uvicorn
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from meteo_proxy import __version__
from meteo_proxy.api.routes import api_router, health_router, root_router
from meteo_proxy.config import get_settings
from meteo_proxy.middleware.logging import LoggingMiddleware, configure_logging


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    # Configure logging
    configure_logging(settings)

    # Create FastAPI app
    app = FastAPI(
        title="Meteo Proxy API",
        description="REST API proxy for Open-Meteo weather data",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add middleware
    app.add_middleware(LoggingMiddleware)

    # Include routers
    app.include_router(root_router)
    app.include_router(api_router)
    app.include_router(health_router)

    # Mount Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


# Create app instance for ASGI servers
app = create_app()


def run() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "meteo_proxy.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
