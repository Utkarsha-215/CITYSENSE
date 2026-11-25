# Sample Payloads & Schemas: Milestone 1

## 1. Open-Meteo Raw Ingestion Batch Envelope

Stored at: `data/raw/weather/YYYY-MM-DD/weather_batch_{batch_id}.json`

```json
{
  "metadata": {
    "batch_id": "8e77c509-e761-45e5-a717-c2c1b85b631e",
    "source_name": "OPEN_METEO_WEATHER_API",
    "ingestion_timestamp": "2026-11-24T16:33:40.587634+00:00",
    "city": "Pune",
    "latitude": 18.5204,
    "longitude": 73.8567,
    "endpoint": "https://api.open-meteo.com/v1/forecast",
    "latency_ms": 2326.32,
    "attribution": "Weather data provided by Open-Meteo.com under CC BY 4.0",
    "ingestion_status": "SUCCESS"
  },
  "raw_payload": {
    "latitude": 18.52,
    "longitude": 73.86,
    "generationtime_ms": 0.087,
    "utc_offset_seconds": 19800,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "IST",
    "elevation": 560.0,
    "hourly_units": {
      "time": "iso8601",
      "temperature_2m": "°C",
      "relative_humidity_2m": "%",
      "rain": "mm",
      "wind_speed_10m": "km/h"
    },
    "hourly": {
      "time": ["2026-11-24T00:00", "2026-11-24T01:00"],
      "temperature_2m": [22.4, 21.8],
      "relative_humidity_2m": [65.0, 68.0],
      "rain": [0.0, 0.0],
      "wind_speed_10m": [8.5, 7.2]
    }
  }
}
```

---

## 2. Unrolled Hourly Weather Record (Validated Format)

```json
{
  "batch_id": "8e77c509-e761-45e5-a717-c2c1b85b631e",
  "city": "Pune",
  "latitude": 18.5204,
  "longitude": 73.8567,
  "timestamp": "2026-11-24T00:00",
  "temperature_2m": 22.4,
  "relative_humidity_2m": 65.0,
  "rain": 0.0,
  "wind_speed_10m": 8.5,
  "source_name": "OPEN_METEO_WEATHER_API",
  "attribution": "Weather data provided by Open-Meteo.com under CC BY 4.0"
}
```

---

## 3. Simulated Traffic Sensor Record

Stored at: `data/raw/traffic/YYYY-MM-DD/traffic_batch_{batch_id}.json`

```json
{
  "sensor_id": "PUN_SNS_001",
  "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
  "road_name": "FC Road",
  "timestamp": "2026-11-24T15:45:12+00:00",
  "vehicle_count": 92,
  "average_speed": 34.2,
  "road_occupancy": 61.33,
  "congestion_level": "MODERATE",
  "data_source_mode": "SIMULATED",
  "simulation_seed": 42
}
```

---

## 4. Quarantined Rejected Record

Stored at: `data/raw/rejected/YYYY-MM-DD/rejected_{source}_batch_{batch_id}.json`

```json
{
  "sensor_id": "PUN_SNS_998",
  "zone_id": "ZONE_IT_HINJEWADI",
  "road_name": "Hinjewadi Phase 1 Main Rd",
  "timestamp": "2026-11-24T16:00:00Z",
  "vehicle_count": -10,
  "average_speed": -5.0,
  "road_occupancy": 150.0,
  "congestion_level": "SEVERE",
  "data_source_mode": "SIMULATED",
  "rejection_reasons": [
    "NEGATIVE_OR_INVALID_VEHICLE_COUNT: 'vehicle_count' must be >= 0, got -10.",
    "INVALID_SPEED_VALUE: 'average_speed' must be between 0.0 and 200.0 km/h, got -5.0.",
    "INVALID_ROAD_OCCUPANCY: 'road_occupancy' must be between 0.0 and 100.0%, got 150.0."
  ]
}
```
