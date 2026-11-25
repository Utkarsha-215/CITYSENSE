"""
CITYSENSE Platform - API Pydantic Response Schemas
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Platform health check and partition discovery model."""
    status: str = Field(..., examples=["HEALTHY"])
    environment: str = Field(..., examples=["development"])
    timestamp: str = Field(..., examples=["2026-11-24T17:00:00Z"])
    available_dates: List[str] = Field(default_factory=list, examples=[["2026-11-24"]])
    total_raw_manifest_batches: int = Field(..., examples=[3])


class ZoneSummary(BaseModel):
    """Aggregated mobility summary for an urban zone."""
    zone_id: str = Field(..., examples=["ZONE_CBD_SHIVAJI_NAGAR"])
    zone_name: str = Field(..., examples=["Shivaji Nagar Central Business District"])
    total_volume: int = Field(..., examples=[1250])
    avg_speed_kmh: float = Field(..., examples=[38.5])
    avg_occupancy_pct: float = Field(..., examples=[52.4])
    avg_congestion_score: float = Field(..., examples=[48.2])
    peak_congestion_score: float = Field(..., examples=[76.5])
    weather_disrupted_events: int = Field(..., examples=[0])
    sensor_count: int = Field(..., examples=[5])


class ZoneKPISchema(BaseModel):
    """Hourly mobility indicator row from Gold aggregate table."""
    zone_id: str = Field(..., examples=["ZONE_CBD_SHIVAJI_NAGAR"])
    observation_hour: str = Field(..., examples=["2026-11-24T15:00:00+00:00"])
    total_vehicle_volume: int = Field(..., examples=[420])
    avg_speed_kmh: float = Field(..., examples=[36.2])
    avg_occupancy_pct: float = Field(..., examples=[58.1])
    avg_congestion_score: float = Field(..., examples=[53.4])
    peak_congestion_score: float = Field(..., examples=[72.0])
    avg_rainfall_mm: float = Field(..., examples=[0.0])
    weather_disrupted_events: int = Field(..., examples=[0])
    sensor_count: int = Field(..., examples=[5])


class CorridorRanking(BaseModel):
    """Corridor congestion severity ranking."""
    sensor_id: str = Field(..., examples=["PUN_SNS_001"])
    zone_id: str = Field(..., examples=["ZONE_CBD_SHIVAJI_NAGAR"])
    road_name: str = Field(..., examples=["FC Road"])
    speed_limit_kmh: float = Field(..., examples=[50.0])
    average_speed_kmh: float = Field(..., examples=[24.5])
    speed_deficit_ratio: float = Field(..., examples=[0.51])
    road_occupancy_pct: float = Field(..., examples=[78.2])
    congestion_score: float = Field(..., examples=[64.6])
    congestion_level: str = Field(..., examples=["HIGH"])
    is_weather_disrupted: bool = Field(..., examples=[False])
    vehicle_count: int = Field(..., examples=[115])


class WeatherImpactMetrics(BaseModel):
    """Metrics under specific weather condition regime."""
    sample_count: int = Field(..., examples=[50])
    avg_speed_kmh: float = Field(..., examples=[42.1])
    avg_occupancy_pct: float = Field(..., examples=[48.0])
    avg_congestion_score: float = Field(..., examples=[41.5])


class WeatherImpactResponse(BaseModel):
    """Quantitative comparison between normal and adverse weather conditions."""
    date: str = Field(..., examples=["2026-11-24"])
    normal_conditions: WeatherImpactMetrics
    disrupted_conditions: WeatherImpactMetrics
    speed_reduction_pct: float = Field(..., examples=[18.5])
    congestion_increase_pct: float = Field(..., examples=[22.3])


class AuditRecord(BaseModel):
    """Data lakehouse batch audit manifest record."""
    batch_id: str = Field(..., examples=["b0849266-8820-4588-af4e-302bb0985752"])
    source_name: str = Field(..., examples=["TRAFFIC"])
    ingestion_timestamp: Optional[str] = Field(None, examples=["2026-11-24T16:32:18Z"])
    partition_date: Optional[str] = Field(None, examples=["2026-11-24"])
    record_count: Optional[int] = Field(None, examples=[10])
    ingestion_status: Optional[str] = Field(None, examples=["SUCCESS"])
    file_name: Optional[str] = Field(None, examples=["traffic_batch_b084.json"])
    sha256_checksum: Optional[str] = Field(None, examples=["72f623ba6..."])
