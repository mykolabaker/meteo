# Real Temperature Proxy API

## Goal

Build a small REST API that fetches current temperature from Open-Meteo and returns a normalized response.

## Integration

Call Open-Meteo Forecast API:

- **Base URL**: `https://api.open-meteo.com/v1/forecast`
- Use the `current` parameter to fetch current conditions

### Example upstream call

```bash
curl "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,wind_speed_10m"
```

## API Response Shape

```json
{
  "location": { "lat": 52.52, "lon": 13.41 },
  "current": {
    "temperatureC": 1.2,
    "windSpeedKmh": 9.7
  },
  "source": "open-meteo",
  "retrievedAt": "2026-01-11T10:12:54Z"
}
```

## Explicit Requirements

1. **Timeout**: 1 second timeout to upstream API
2. **Caching**: Cache by (lat, lon) for 60 seconds
3. **Production-ready features**:
   - Kubernetes containerization
   - Health checks
   - Resource limits
   - Configuration (timeouts, cache TTLs)
   - Scaling support

## Technology

- Implementation language: **Python**
