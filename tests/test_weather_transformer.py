"""
CITYSENSE Platform - Weather Transformer Unit Tests
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from src.processing.weather_transformer import WeatherTransformer


class TestWeatherTransformer:
    """Test suite for Weather Bronze-to-Silver transformation and deduplication."""

    def test_weather_transformation_and_deduplication(self, tmp_path: Path):
        base_dir = tmp_path / "data"
        raw_dir = base_dir / "raw" / "weather" / "2026-11-24"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Batch 1: Two hourly records
        batch_1 = {
            "metadata": {
                "batch_id": "b1",
                "city": "Pune",
                "latitude": 18.52,
                "longitude": 73.86,
                "ingestion_timestamp": "2026-11-24T10:00:00+00:00",
            },
            "raw_payload": {
                "hourly": {
                    "time": ["2026-11-24T00:00", "2026-11-24T01:00"],
                    "temperature_2m": [20.0, 21.0],
                    "relative_humidity_2m": [70.0, 68.0],
                    "rain": [0.0, 0.5],
                    "wind_speed_10m": [10.0, 12.0],
                }
            },
        }

        # Batch 2: Duplicate 01:00 timestamp with updated temperature + new 02:00 timestamp
        batch_2 = {
            "metadata": {
                "batch_id": "b2",
                "city": "Pune",
                "latitude": 18.52,
                "longitude": 73.86,
                "ingestion_timestamp": "2026-11-24T11:00:00+00:00",
            },
            "raw_payload": {
                "hourly": {
                    "time": ["2026-11-24T01:00", "2026-11-24T02:00"],
                    "temperature_2m": [21.5, 22.0],  # Updated reading
                    "relative_humidity_2m": [67.0, 65.0],
                    "rain": [0.2, 0.0],
                    "wind_speed_10m": [11.0, 9.0],
                }
            },
        }

        with open(raw_dir / "weather_batch_b1.json", "w", encoding="utf-8") as f:
            json.dump(batch_1, f)
        with open(raw_dir / "weather_batch_b2.json", "w", encoding="utf-8") as f:
            json.dump(batch_2, f)

        transformer = WeatherTransformer(base_data_dir=base_dir)
        metrics = transformer.transform_partition("2026-11-24")

        assert metrics["status"] == "SUCCESS"
        assert metrics["raw_records_count"] == 4
        assert metrics["silver_records_count"] == 3  # 00:00, 01:00, 02:00
        assert metrics["duplicates_dropped"] == 1

        # Verify Parquet file contents
        out_file = Path(metrics["output_path"])
        assert out_file.exists()
        df = pd.read_parquet(out_file)
        assert len(df) == 3

        # Check that latest batch (b2) won for 01:00 timestamp
        row_01 = df[df["timestamp"] == pd.Timestamp("2026-11-24T01:00:00+00:00")].iloc[0]
        assert row_01["source_batch_id"] == "b2"
        assert row_01["temperature_celsius"] == pytest.approx(21.5, rel=1e-3)
