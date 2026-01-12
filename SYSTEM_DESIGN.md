# System Design Document: Real Temperature Proxy API

## 1. Overview

A lightweight REST API proxy service that fetches current weather data from Open-Meteo and returns normalized responses. The service is designed to be production-ready with proper caching, error handling, observability, and Kubernetes deployment support.

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Clients   │────▶│  Meteo Proxy API │────▶│  Open-Meteo API │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │    Cache     │
                    │  (In-Memory) │
                    └──────────────┘
```

### 2.2 Component Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Meteo Proxy API                           │
├────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Router    │  │ Middleware  │  │     Health Checks       │ │
│  │  (FastAPI)  │  │  (Logging,  │  │  (Liveness/Readiness)   │ │
│  │             │  │   Metrics)  │  │                         │ │
│  └──────┬──────┘  └─────────────┘  └─────────────────────────┘ │
│         │                                                      │
│  ┌──────▼──────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Handlers   │  │   Cache     │  │    Configuration        │ │
│  │             │──│  Service    │  │    (Pydantic Settings)  │ │
│  └──────┬──────┘  └─────────────┘  └─────────────────────────┘ │
│         │                                                      │
│  ┌──────▼──────┐                                               │
│  │ Open-Meteo  │                                               │
│  │   Client    │                                               │
│  └─────────────┘                                               │
└────────────────────────────────────────────────────────────────┘
```

## 3. API Design

### 3.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/weather` | Get current weather for coordinates |
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe |
| GET | `/metrics` | Prometheus metrics |

### 3.2 Weather Endpoint

**Request:**
```
GET /api/v1/weather?lat={latitude}&lon={longitude}
```

**Query Parameters:**
| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| lat | float | Yes | Latitude | -90 to 90 |
| lon | float | Yes | Longitude | -180 to 180 |

**Success Response (200 OK):**
```json
{
  "location": {
    "lat": 52.52,
    "lon": 13.41
  },
  "current": {
    "temperatureC": 1.2,
    "windSpeedKmh": 9.7
  },
  "source": "open-meteo",
  "retrievedAt": "2026-01-11T10:12:54Z"
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| 400 | Invalid coordinates |
| 502 | Upstream API error |
| 503 | Service unavailable |
| 504 | Upstream timeout |

**Error Response Body:**
```json
{
  "error": {
    "code": "UPSTREAM_TIMEOUT",
    "message": "Open-Meteo API request timed out"
  }
}
```

### 3.3 Health Endpoints

**Liveness Probe (GET /health/live):**
```json
{
  "status": "ok"
}
```

**Readiness Probe (GET /health/ready):**
```json
{
  "status": "ok",
  "checks": {
    "cache": "ok"
  }
}
```

## 4. Technical Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | FastAPI | Async support, automatic OpenAPI docs, validation |
| HTTP Client | httpx | Async HTTP client with timeout support |
| Cache | cachetools (TTLCache) | Simple in-memory TTL cache |
| Configuration | pydantic-settings | Type-safe configuration with env vars |
| Server | uvicorn | ASGI server with good performance |
| Metrics | prometheus-client | Standard metrics format |
| Containerization | Docker | Industry standard |
| Orchestration | Kubernetes | Scaling, health checks, resource management |

## 5. Caching Strategy

### 5.1 Cache Key Design

Cache key format: `weather:{lat_rounded}:{lon_rounded}`

Coordinates are rounded to 2 decimal places (~1.1km precision) to improve cache hit rate while maintaining reasonable accuracy.

### 5.2 Cache Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| TTL | 60 seconds | Cache entry lifetime |
| Max Size | 10,000 entries | Maximum cache entries |

### 5.3 Cache Behavior

- **Cache Hit**: Return cached response immediately
- **Cache Miss**: Fetch from upstream, cache response, return
- **Cache Invalidation**: Automatic TTL-based expiration

## 6. Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | 0.0.0.0 | Server bind host |
| `APP_PORT` | 8080 | Server bind port |
| `UPSTREAM_URL` | https://api.open-meteo.com/v1/forecast | Open-Meteo API URL |
| `UPSTREAM_TIMEOUT_SECONDS` | 1.0 | Upstream request timeout |
| `CACHE_TTL_SECONDS` | 60 | Cache TTL |
| `CACHE_MAX_SIZE` | 10000 | Max cache entries |
| `LOG_LEVEL` | INFO | Logging level |
| `LOG_FORMAT` | json | Log format (json/text) |

## 7. Error Handling

### 7.1 Error Categories

| Category | HTTP Status | Recovery |
|----------|-------------|----------|
| Validation Error | 400 | Client fixes request |
| Upstream Timeout | 504 | Retry with backoff |
| Upstream Error | 502 | Check upstream status |
| Internal Error | 500 | Alert, investigate |

### 7.2 Upstream Failure Handling

1. **Timeout**: Return 504 immediately after timeout threshold
2. **5xx from upstream**: Return 502 with error details
3. **Rate limiting**: Return 503 with Retry-After header if upstream provides it

## 8. Observability

### 8.1 Logging

Structured JSON logging with:
- Request ID
- Timestamp
- Log level
- Message
- Context (lat, lon, cache_hit, response_time_ms)

**Example log entry:**
```json
{
  "timestamp": "2026-01-11T10:12:54.123Z",
  "level": "INFO",
  "request_id": "abc123",
  "message": "Weather request completed",
  "context": {
    "lat": 52.52,
    "lon": 13.41,
    "cache_hit": false,
    "response_time_ms": 245
  }
}
```

### 8.2 Metrics (Prometheus)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, path, status | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | method, path | Request latency |
| `upstream_requests_total` | Counter | status | Upstream API calls |
| `upstream_request_duration_seconds` | Histogram | - | Upstream latency |
| `cache_hits_total` | Counter | - | Cache hit count |
| `cache_misses_total` | Counter | - | Cache miss count |
| `cache_size` | Gauge | - | Current cache entries |

### 8.3 Health Checks

**Liveness**: Basic process health check
**Readiness**: Verifies cache is operational

## 9. Kubernetes Deployment

### 9.1 Resource Specifications

```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "128Mi"
    cpu: "200m"
```

### 9.2 Scaling

- **Horizontal Pod Autoscaler (HPA)** based on CPU/memory
- Min replicas: 2 (for HA)
- Max replicas: 10

### 9.3 Deployment Strategy

- Rolling update with maxSurge: 1, maxUnavailable: 0
- Readiness probe must pass before receiving traffic

### 9.4 Kubernetes Resources

| Resource | Purpose |
|----------|---------|
| Deployment | Application pods |
| Service | Internal load balancing |
| ConfigMap | Non-sensitive configuration |
| HPA | Auto-scaling |
| PodDisruptionBudget | HA during maintenance |

## 10. Security Considerations

### 10.1 Container Security

- Non-root user in container
- Read-only root filesystem
- No privilege escalation
- Minimal base image (python:3.12-slim)

### 10.2 Network Security

- No sensitive data in logs
- HTTPS for upstream calls (enforced)
- Request validation to prevent injection

## 11. Project Structure

```
meteo-proxy/
├── src/
│   └── meteo_proxy/
│       ├── __init__.py
│       ├── main.py              # Application entry point
│       ├── config.py            # Configuration management
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py        # API route definitions
│       │   ├── schemas.py       # Pydantic models
│       │   └── dependencies.py  # FastAPI dependencies
│       ├── services/
│       │   ├── __init__.py
│       │   ├── weather.py       # Weather service logic
│       │   ├── cache.py         # Cache implementation
│       │   └── open_meteo.py    # Open-Meteo client
│       └── middleware/
│           ├── __init__.py
│           └── logging.py       # Logging middleware
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Test fixtures
│   ├── test_api.py              # API tests
│   ├── test_cache.py            # Cache tests
│   └── test_open_meteo.py       # Client tests
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml
│   └── pdb.yaml
├── Dockerfile
├── docker-compose.yaml          # Local development
├── pyproject.toml               # Project metadata & dependencies
├── TASK.md
├── SYSTEM_DESIGN.md
└── README.md
```

## 12. Dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "httpx>=0.26.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "cachetools>=5.3.0",
    "prometheus-client>=0.19.0",
    "structlog>=24.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",  # For TestClient
    "respx>=0.20.0",  # Mock httpx
    "ruff>=0.1.0",    # Linting
    "mypy>=1.8.0",    # Type checking
]
```

## 13. Testing Strategy

### 13.1 Test Categories

| Type | Coverage Target | Focus |
|------|-----------------|-------|
| Unit | 90%+ | Services, cache, validation |
| Integration | Key paths | API endpoints, upstream mocking |
| Load | N/A | Performance validation |

### 13.2 Key Test Scenarios

1. **Happy path**: Valid coordinates return weather data
2. **Cache hit**: Second request returns cached data
3. **Upstream timeout**: Proper 504 response
4. **Invalid coordinates**: 400 with validation error
5. **Upstream error**: 502 with error details

## 14. Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run locally
uvicorn meteo_proxy.main:app --reload

# Run tests
pytest

# Lint & type check
ruff check .
mypy src/
```

## 15. Deployment Checklist

- [ ] Docker image builds successfully
- [ ] All tests pass
- [ ] Health endpoints respond correctly
- [ ] Metrics endpoint exposes expected metrics
- [ ] Resource limits are appropriate
- [ ] HPA configuration tested
- [ ] Logging format is correct (JSON)
- [ ] Configuration via env vars works
