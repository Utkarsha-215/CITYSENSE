# CITYSENSE Data Dictionary: Medallion Architecture

---

## 1. Bronze Layer (Raw Landing Zone)

Stored in date partitions as immutable raw JSON envelopes (`data/raw/<source>/YYYY-MM-DD/`):

### Weather Raw Envelope (`data/raw/weather/YYYY-MM-DD/weather_batch_{id}.json`)
- `metadata.batch_id` (string, UUIDv4): Unique ingestion batch identifier.
- `metadata.source_name` (string): Constant `OPEN_METEO_WEATHER_API`.
- `metadata.city` (string): Observation target city (e.g. `Pune`).
- `metadata.latitude` (float): Latitude coordinate.
- `metadata.longitude` (float): Longitude coordinate.
- `metadata.ingestion_timestamp` (string, ISO-8601): UTC ingestion timestamp.
- `metadata.latency_ms` (float): API request round-trip time in milliseconds.
- `metadata.attribution` (string): Open-Meteo CC BY 4.0 license attribution.
- `raw_payload` (object): Unmodified Open-Meteo JSON response payload.

### Traffic Raw Envelope (`data/raw/traffic/YYYY-MM-DD/traffic_batch_{id}.json`)
- `metadata.batch_id` (string, UUIDv4): Unique ingestion batch identifier.
- `metadata.source_name` (string): Constant `TRAFFIC_SENSOR_SIMULATOR`.
- `metadata.data_source_mode` (string): Constant `SIMULATED`.
- `metadata.simulation_seed` (int): Reproducibility seed.
- `metadata.ingestion_timestamp` (string, ISO-8601): UTC ingestion timestamp.
- `metadata.record_count` (int): Number of sensor readings.
- `records` (array of objects): Array of raw sensor records.

---

## 2. Silver Layer (Cleaned & Standardized Parquet)

Stored in columnar Apache Parquet format (`data/processed/<source>/date=YYYY-MM-DD/`):

### Traffic Silver Table (`traffic_silver.parquet`)

| Column Name | PyArrow Data Type | Nullable | Description |
|:---|:---|:---|:---|
| `sensor_id` | `string` | No | Unique sensor identifier (e.g. `PUN_SNS_001`). Part of primary key. |
| `zone_id` | `string` | No | Urban zone code (e.g. `ZONE_CBD_SHIVAJI_NAGAR`). |
| `road_name` | `string` | No | Name of the road corridor (e.g. `FC Road`). |
| `timestamp` | `timestamp[ns, tz=UTC]` | No | Sensor observation timestamp in UTC. Part of primary key. |
| `vehicle_count` | `int32` | No | Non-negative count of vehicles observed in the sampling interval. |
| `average_speed_kmh` | `float32` | No | Average vehicular speed in km/h. |
| `road_occupancy_pct` | `float32` | No | Percentage of road capacity occupied (0.0 to 100.0%). |
| `congestion_level` | `string` | No | Congestion tier (`LOW`, `MODERATE`, `HIGH`, `SEVERE`). |
| `data_source_mode` | `string` | No | Label denoting `SIMULATED` origin. |
| `source_batch_id` | `string` | No | Ingestion batch ID tracking data lineage. |
| `ingested_at` | `timestamp[ns, tz=UTC]` | No | Timestamp when the raw batch was originally ingested. |

### Weather Silver Table (`weather_silver.parquet`)

| Column Name | PyArrow Data Type | Nullable | Description |
|:---|:---|:---|:---|
| `timestamp` | `timestamp[ns, tz=UTC]` | No | Hourly weather observation timestamp in UTC. Primary key component. |
| `city` | `string` | No | City name (e.g. `Pune`). Primary key component. |
| `latitude` | `float32` | No | Observation latitude coordinate. |
| `longitude` | `float32` | No | Observation longitude coordinate. |
| `temperature_celsius` | `float32` | Yes | Ambient air temperature at 2 meters above ground in °C. |
| `relative_humidity_pct` | `float32` | Yes | Relative humidity at 2 meters in % (0.0 to 100.0%). |
| `rainfall_mm` | `float32` | Yes | Precipitation/rain amount in mm. |
| `wind_speed_kmh` | `float32` | Yes | Wind speed at 10 meters in km/h. |
| `source_batch_id` | `string` | No | Ingestion batch ID tracking data lineage. |
| `ingested_at` | `timestamp[ns, tz=UTC]` | No | Ingestion timestamp. |

---

## 3. Gold Layer (Curated Analytical Intelligence)

Stored in columnar Apache Parquet format (`data/curated/<table_name>/date=YYYY-MM-DD/`):

### Fact Table: `fact_traffic_weather_hourly`

| Column Name | Type | Description |
|:---|:---|:---|
| `sensor_id` | `string` | Sensor identifier. |
| `zone_id` | `string` | Urban zone code. |
| `road_name` | `string` | Road corridor name. |
| `timestamp` | `timestamp[ns, tz=UTC]` | Exact observation timestamp. |
| `observation_hour` | `timestamp[ns, tz=UTC]` | Hourly bucket used for spatiotemporal cross-domain join. |
| `vehicle_count` | `int32` | Vehicle throughput in the sampling window. |
| `average_speed_kmh` | `float32` | Observed vehicular speed. |
| `speed_limit_kmh` | `float32` | Legal road corridor speed limit from zone metadata. |
| `road_occupancy_pct` | `float32` | Road capacity occupancy percentage. |
| `congestion_level` | `string` | Qualitative congestion category. |
| `speed_deficit_ratio` | `float32` | $\max\left(0, \frac{\text{speed\_limit} - \text{average\_speed}}{\text{speed\_limit}}\right)$. |
| `congestion_score` | `float32` | Composite mobility score ($0.5 \times \text{occupancy} + 0.5 \times (\text{speed\_deficit} \times 100)$), bounded $[0, 100]$. |
| `temperature_celsius` | `float32` | Prevailing ambient temperature. |
| `relative_humidity_pct` | `float32` | Prevailing relative humidity. |
| `rainfall_mm` | `float32` | Hourly rainfall accumulation in mm. |
| `wind_speed_kmh` | `float32` | Hourly wind speed in km/h. |
| `is_weather_disrupted` | `boolean` | Flag indicating weather severity ($\text{rainfall} > 1.0\text{ mm} \lor \text{wind} > 30\text{ km/h}$). |
| `estimated_hourly_throughput` | `int32` | Projected vehicle capacity throughput per hour. |

### Aggregate Table: `agg_zone_mobility_kpis`

| Column Name | Type | Description |
|:---|:---|:---|
| `zone_id` | `string` | Urban zone identifier. |
| `observation_hour` | `timestamp[ns, tz=UTC]` | Hourly reporting interval. |
| `total_vehicle_volume` | `int32` | Sum of vehicle observations across all sensors in the zone. |
| `avg_speed_kmh` | `float32` | Mean vehicular speed across the zone. |
| `avg_occupancy_pct` | `float32` | Mean road occupancy across all monitored corridors. |
| `avg_congestion_score` | `float32` | Mean mobility congestion score for the zone. |
| `peak_congestion_score` | `float32` | Maximum congestion score recorded by any sensor in the zone. |
| `avg_rainfall_mm` | `float32` | Average rainfall recorded during the hour. |
| `weather_disrupted_events` | `int32` | Count of sensor observations classified as weather-disrupted. |
| `sensor_count` | `int32` | Number of distinct sensors reporting data in the zone. |
