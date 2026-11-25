# CITYSENSE REST API Reference

The CITYSENSE Serving Layer is built on **FastAPI** and provides sub-millisecond querying over the Gold curated and Silver cleansed Parquet data lakehouse tables.

---

## Base URL
```text
http://localhost:8000
```

Interactive OpenAPI Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Endpoints

### 1. Health & Platform Status
`GET /api/v1/health`

Returns operational health status, active environment, and discovered date partitions in the lakehouse.

#### Response: `200 OK`
```json
{
  "status": "HEALTHY",
  "environment": "development",
  "timestamp": "2026-11-24T17:00:00.000000Z",
  "available_dates": ["2026-11-24"],
  "total_raw_manifest_batches": 3
}
```

---

### 2. Urban Mobility Zone Summaries
`GET /api/v1/mobility/zones`

Retrieves summarized vehicular volume, average speed, road occupancy, and congestion index across all monitored smart city zones.

#### Query Parameters:
- `date` (optional, string): Date partition formatted as `YYYY-MM-DD`. Defaults to latest available partition.

#### Response: `200 OK`
```json
[
  {
    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
    "zone_name": "Shivaji Nagar Central Business District",
    "total_volume": 420,
    "avg_speed_kmh": 36.2,
    "avg_occupancy_pct": 58.1,
    "avg_congestion_score": 53.4,
    "peak_congestion_score": 72.0,
    "weather_disrupted_events": 0,
    "sensor_count": 5
  }
]
```

---

### 3. Zone Hourly KPIs Timeseries
`GET /api/v1/mobility/zones/{zone_id}/kpis`

Retrieves hourly mobility indicator series for a specified zone.

#### Path Parameters:
- `zone_id` (required, string): Urban zone identifier (e.g. `ZONE_CBD_SHIVAJI_NAGAR`, `ZONE_IT_HINJEWADI`).

#### Query Parameters:
- `date` (optional, string): Target date partition.

#### Response: `200 OK`
```json
[
  {
    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
    "observation_hour": "2026-11-24T15:00:00+00:00",
    "total_vehicle_volume": 120,
    "avg_speed_kmh": 34.2,
    "avg_occupancy_pct": 61.3,
    "avg_congestion_score": 55.4,
    "peak_congestion_score": 71.0,
    "avg_rainfall_mm": 0.0,
    "weather_disrupted_events": 0,
    "sensor_count": 5
  }
]
```

#### Error Response: `404 Not Found`
```json
{
  "detail": "Zone 'INVALID_ZONE' not found or no KPI data available for date 'latest'"
}
```

---

### 4. Corridor Congestion Rankings
`GET /api/v1/mobility/corridors/congestion`

Ranks smart city road corridors by congestion severity score ($\in [0, 100]$) and speed deficit ratio.

#### Query Parameters:
- `date` (optional, string): Target date partition.
- `limit` (optional, integer): Max records to return (1 to 50, default: 10).

#### Response: `200 OK`
```json
[
  {
    "sensor_id": "PUN_SNS_001",
    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
    "road_name": "FC Road",
    "speed_limit_kmh": 50.0,
    "average_speed_kmh": 22.5,
    "speed_deficit_ratio": 0.55,
    "road_occupancy_pct": 82.4,
    "congestion_score": 68.7,
    "congestion_level": "HIGH",
    "is_weather_disrupted": false,
    "vehicle_count": 135
  }
]
```

---

### 5. Weather-Mobility Impact Analysis
`GET /api/v1/analytics/weather-impact`

Quantifies the velocity and congestion delta between normal dry weather vs adverse weather conditions (precipitation $> 1.0\text{ mm}$ or wind speed $> 30\text{ km/h}$).

#### Response: `200 OK`
```json
{
  "date": "2026-11-24",
  "normal_conditions": {
    "sample_count": 10,
    "avg_speed_kmh": 41.2,
    "avg_occupancy_pct": 49.5,
    "avg_congestion_score": 44.8
  },
  "disrupted_conditions": {
    "sample_count": 2,
    "avg_speed_kmh": 31.0,
    "avg_occupancy_pct": 68.0,
    "avg_congestion_score": 62.0
  },
  "speed_reduction_pct": 24.8,
  "congestion_increase_pct": 38.4
}
```

---

### 6. Lakehouse Audit Manifests
- `GET /api/v1/audit/ingestion?limit=50`: Returns Bronze raw batch lineage records with SHA-256 data integrity checksums.
- `GET /api/v1/audit/processing?limit=50`: Returns Medallion transformation processing logs and dropped duplicate metrics.
