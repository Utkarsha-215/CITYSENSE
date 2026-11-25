"""
CITYSENSE Platform - Traffic Transformer Unit Tests
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from src.processing.traffic_transformer import TrafficTransformer


class TestTrafficTransformer:
    """Test suite for Traffic Bronze-to-Silver transformation and deduplication."""

    def test_traffic_transformation_and_deduplication(self, tmp_path: Path):
        base_dir = tmp_path / "data"
        raw_dir = base_dir / "raw" / "traffic" / "2026-11-24"
        raw_dir.mkdir(parents=True, exist_ok=True)

        batch_1 = {
            "metadata": {
                "batch_id": "b1",
                "ingestion_timestamp": "2026-11-24T10:00:00+00:00",
            },
            "records": [
                {
                    "sensor_id": "PUN_SNS_001",
                    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
                    "road_name": "FC Road",
                    "timestamp": "2026-11-24T10:15:00+00:00",
                    "vehicle_count": 80,
                    "average_speed": 40.0,
                    "road_occupancy": 53.3,
                    "congestion_level": "MODERATE",
                    "data_source_mode": "SIMULATED",
                },
                {
                    "sensor_id": "PUN_SNS_002",
                    "zone_id": "ZONE_IT_HINJEWADI",
                    "road_name": "Hinjewadi Phase 1 Main Rd",
                    "timestamp": "2026-11-24T10:15:00+00:00",
                    "vehicle_count": 150,
                    "average_speed": 25.0,
                    "road_occupancy": 75.0,
                    "congestion_level": "HIGH",
                    "data_source_mode": "SIMULATED",
                },
            ],
        }

        # Duplicate of PUN_SNS_001 at 10:15 in batch 2
        batch_2 = {
            "metadata": {
                "batch_id": "b2",
                "ingestion_timestamp": "2026-11-24T10:05:00+00:00",
            },
            "records": [
                {
                    "sensor_id": "PUN_SNS_001",
                    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
                    "road_name": "FC Road",
                    "timestamp": "2026-11-24T10:15:00+00:00",
                    "vehicle_count": 85,
                    "average_speed": 38.0,
                    "road_occupancy": 55.0,
                    "congestion_level": "MODERATE",
                    "data_source_mode": "SIMULATED",
                }
            ],
        }

        with open(raw_dir / "traffic_batch_b1.json", "w", encoding="utf-8") as f:
            json.dump(batch_1, f)
        with open(raw_dir / "traffic_batch_b2.json", "w", encoding="utf-8") as f:
            json.dump(batch_2, f)

        transformer = TrafficTransformer(base_data_dir=base_dir)
        metrics = transformer.transform_partition("2026-11-24")

        assert metrics["status"] == "SUCCESS"
        assert metrics["raw_records_count"] == 3
        assert metrics["silver_records_count"] == 2
        assert metrics["duplicates_dropped"] == 1

        out_file = Path(metrics["output_path"])
        assert out_file.exists()
        df = pd.read_parquet(out_file)
        assert len(df) == 2

        # Check types
        assert str(df["vehicle_count"].dtype) == "int32"
        assert str(df["average_speed_kmh"].dtype) == "float32"
        assert str(df["road_occupancy_pct"].dtype) == "float32"

        # Check latest record kept
        row_sns1 = df[df["sensor_id"] == "PUN_SNS_001"].iloc[0]
        assert row_sns1["source_batch_id"] == "b2"
        assert row_sns1["vehicle_count"] == 85
