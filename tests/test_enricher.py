"""
CITYSENSE Platform - SpatioTemporal Enricher Unit Tests
"""

from pathlib import Path
import pandas as pd
import pytest

from src.processing.enricher import SpatioTemporalEnricher


class TestSpatioTemporalEnricher:
    """Test suite for Silver-to-Gold spatiotemporal joining and KPI calculations."""

    def test_enrichment_and_kpi_calculations(self, tmp_path: Path, sample_zones_config):
        base_dir = tmp_path / "data"

        # Create Silver Traffic Parquet
        traffic_dir = base_dir / "processed" / "traffic" / "date=2026-11-24"
        traffic_dir.mkdir(parents=True, exist_ok=True)

        traffic_data = pd.DataFrame([
            {
                "sensor_id": "PUN_SNS_001",
                "zone_id": "ZONE_TEST_A",  # Speed limit = 60.0 km/h in sample_zones_config
                "road_name": "Alpha Expressway",
                "timestamp": pd.Timestamp("2026-11-24 14:15:00", tz="UTC"),
                "vehicle_count": 80,
                "average_speed_kmh": 30.0,
                "road_occupancy_pct": 60.0,
                "congestion_level": "MODERATE",
                "data_source_mode": "SIMULATED",
                "source_batch_id": "b1",
                "ingested_at": pd.Timestamp("2026-11-24 14:20:00", tz="UTC"),
            },
            {
                "sensor_id": "PUN_SNS_002",
                "zone_id": "ZONE_TEST_A",
                "road_name": "Beta Boulevard",
                "timestamp": pd.Timestamp("2026-11-24 14:45:00", tz="UTC"),
                "vehicle_count": 40,
                "average_speed_kmh": 55.0,
                "road_occupancy_pct": 25.0,
                "congestion_level": "LOW",
                "data_source_mode": "SIMULATED",
                "source_batch_id": "b1",
                "ingested_at": pd.Timestamp("2026-11-24 14:50:00", tz="UTC"),
            },
        ])
        traffic_data.to_parquet(traffic_dir / "traffic_silver.parquet")

        # Create Silver Weather Parquet
        weather_dir = base_dir / "processed" / "weather" / "date=2026-11-24"
        weather_dir.mkdir(parents=True, exist_ok=True)

        weather_data = pd.DataFrame([
            {
                "timestamp": pd.Timestamp("2026-11-24 14:00:00", tz="UTC"),
                "city": "Pune",
                "latitude": 18.52,
                "longitude": 73.86,
                "temperature_celsius": 24.5,
                "relative_humidity_pct": 85.0,
                "rainfall_mm": 3.5,  # Heavy rain triggers disruption
                "wind_speed_kmh": 15.0,
                "source_batch_id": "bw1",
                "ingested_at": pd.Timestamp("2026-11-24 14:05:00", tz="UTC"),
            }
        ])
        weather_data.to_parquet(weather_dir / "weather_silver.parquet")

        enricher = SpatioTemporalEnricher(
            base_data_dir=base_dir,
            zones_config_path=sample_zones_config,
        )
        metrics = enricher.enrich_partition("2026-11-24")

        assert metrics["status"] == "SUCCESS"
        assert metrics["fact_records_count"] == 2
        assert metrics["agg_records_count"] == 1

        # Inspect Fact Parquet
        df_fact = pd.read_parquet(metrics["fact_output_path"])
        assert len(df_fact) == 2

        # Check Speed Deficit Ratio for row 1: (60 - 30) / 60 = 0.5
        row_1 = df_fact.iloc[0]
        assert row_1["speed_limit_kmh"] == 60.0
        assert row_1["speed_deficit_ratio"] == pytest.approx(0.5, rel=1e-3)

        # Check Congestion Score: 0.5 * 60 + 0.5 * (0.5 * 100) = 30 + 25 = 55.0
        assert row_1["congestion_score"] == pytest.approx(55.0, rel=1e-2)

        # Check Weather Disruption Flag: rainfall_mm = 3.5 > 1.0 -> True
        assert bool(row_1["is_weather_disrupted"]) is True
        assert row_1["rainfall_mm"] == pytest.approx(3.5, rel=1e-3)

        # Inspect Aggregated Parquet
        df_agg = pd.read_parquet(metrics["agg_output_path"])
        assert len(df_agg) == 1
        agg_row = df_agg.iloc[0]
        assert agg_row["zone_id"] == "ZONE_TEST_A"
        assert agg_row["total_vehicle_volume"] == 120  # 80 + 40
        assert agg_row["sensor_count"] == 2
        assert agg_row["weather_disrupted_events"] == 2
