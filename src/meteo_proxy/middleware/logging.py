"""Logging middleware and configuration."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from meteo_proxy.config import Settings

# Map log level names to logging module constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Metrics
http_requests = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


def configure_logging(settings: Settings) -> None:
    """Configure structlog based on settings."""
    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    log_level = LOG_LEVELS.get(settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and metrics."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with logging and metrics."""
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request_id_var.set(request_id)

        # Bind request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger = structlog.get_logger()

        # Record start time
        start_time = time.perf_counter()

        # Process request
        try:
            response = await call_next(request)
        except Exception:
            # Log error and re-raise
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Request failed with exception", duration_ms=round(duration_ms, 2))
            http_requests.labels(
                method=request.method,
                path=request.url.path,
                status="500",
            ).inc()
            raise

        # Calculate duration
        duration = time.perf_counter() - start_time
        duration_ms = duration * 1000

        # Record metrics
        http_requests.labels(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        ).inc()
        http_duration.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration)

        # Log request completion
        logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
