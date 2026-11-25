# Technical Architecture Specification: Milestone 1

## Ingestion Architecture & Resilience Engineering

CITYSENSE Milestone 1 establishes the landing zone and data quality boundary for the platform.

### 1. Resilience & Retry Strategy

The `WeatherIngestionClient` communicates with the Open-Meteo REST API over HTTP. Network flakiness, rate limits, or transient downstream errors are managed through:
- **Urllib3 Retry Strategy**:
  - `total=3`: Retries up to 3 times on transient failures.
  - `backoff_factor=0.5`: Applies exponential backoff delays ($0.5s \times 2^{(\text{retry}-1)}$: 0.5s, 1.0s, 2.0s).
  - `status_forcelist=[429, 500, 502, 503, 504]`: Targets rate-limiting and server-side errors specifically.
- **Connection & Read Timeouts**:
  - Separate connection timeout (5.0s) and read timeout (15.0s) preventing indefinite socket hang.
- **Granular Exception Hierarchy**:
  - `WeatherAPIConnectionError`: Network drops, DNS lookup failures, timeouts.
  - `WeatherAPIHTTPError`: Explicit 4xx / 5xx HTTP response codes.
  - `WeatherAPIDataError`: Malformed JSON or schema drift.

---

### 2. Traffic Mobility Simulation Model

The `TrafficSensorSimulator` generates synthetic vehicular observations designed to model realistic urban traffic dynamics across 5 designated Pune corridors:

$$\text{Density} = \begin{cases} 
\mathcal{U}(0.65, 0.98) & \text{if rush hour (08:00--11:00 or 17:00--20:00)} \\ 
\mathcal{U}(0.15, 0.60) & \text{otherwise} 
\end{cases}$$

$$\text{Vehicle Count} = \max\left(0, \left\lfloor \text{Capacity} \times \text{Density} \times \mathcal{U}(0.85, 1.15) \right\rceil\right)$$

$$\text{Road Occupancy} = \min\left(100.0, \max\left(0.0, \frac{\text{Vehicle Count}}{\text{Capacity}} \times 100.0 \times \mathcal{U}(0.90, 1.05)\right)\right)$$

Congestion levels and average speeds are dynamically coupled to road occupancy:
- **Occupancy > 85%**: `SEVERE` congestion, speed crawls at 5.0--15.0 km/h.
- **Occupancy 65%--85%**: `HIGH` congestion, speed drops to 15.0 km/h -- 55% of speed limit.
- **Occupancy 40%--65%**: `MODERATE` congestion, speed is 55%--85% of speed limit.
- **Occupancy < 40%**: `LOW` congestion, free flow at 85%--110% of speed limit.

All records are tagged with `"data_source_mode": "SIMULATED"` and the active RNG seed for byte-level auditability.

---

### 3. Data Storage & Immutability Guarantees

Raw data persistence adheres to standard data lake ingestion patterns:
1. **Partitioning**: Date partitions formatted as `YYYY-MM-DD` ensure efficient downstream partition pruning.
2. **Batch Identification**: Every ingestion run is assigned a globally unique `UUIDv4` (`batch_id`).
3. **Strict Non-Overwrite**: The `RawStorageManager` checks for file existence prior to writing; if a batch file exists, it raises `BatchAlreadyExistsError`.
4. **Data Integrity Audit**: Every written batch computes a SHA-256 hash stored in `data/raw/ingestion_manifest.jsonl`.
5. **Dead-Letter / Quarantine Store**: Rejected records failing schema or physical boundary checks are isolated into `data/raw/rejected/YYYY-MM-DD/` with complete diagnostic reasons.
