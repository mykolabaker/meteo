# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir build

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Build wheel
RUN python -m build --wheel


# Runtime stage
FROM python:3.12-slim

# Security: Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy wheel from builder
COPY --from=builder /app/dist/*.whl .

# Install the application
RUN pip install --no-cache-dir *.whl && rm *.whl

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health/live')" || exit 1

# Run application
CMD ["python", "-m", "meteo_proxy.main"]
