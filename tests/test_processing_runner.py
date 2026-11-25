"""
CITYSENSE Platform - Processing Pipeline Orchestrator Integration Tests
"""

from pathlib import Path
import json
import pytest

from src.processing.runner import ProcessingPipelineOrchestrator


class TestProcessingPipelineOrchestrator:
    """Integration test suite for the Medallion pipeline runner."""

    def test_run_pipeline_end_to_end(self, tmp_path: Path, sample_zones_config):
        base_dir = tmp_path / "data"
        date_str = "2026-11-24"

        # Create Raw Weather batch
        raw_w_dir = base_dir / "raw" / "weather" / date_str
        raw_w_dir.mkdir(parents=True, exist_ok=True)
        w_batch = {
            "metadata": {"batch_id": "wb-01", "city": "Pune", "ingestion_timestamp": "2026-11-24T12:00:00Z"},
            "raw_payload": {
                "hourly": {
                    "time": ["2026-11-24T12:00"],
                    "temperature_2m": [26.0],
                    "relative_humidity_2m": [50.0],
                    "rain": [0.0],
                    "wind_speed_10m": [10.0],
                }
            },
        }
        with open(raw_w_dir / "weather_batch_wb-01.json", "w", encoding="utf-8") as f:
            json.dump(w_batch, f)

        # Create Raw Traffic batch
        raw_t_dir = base_dir / "raw" / "traffic" / date_str
        raw_t_dir.mkdir(parents=True, exist_ok=True)
        t_batch = {
            "metadata": {"batch_id": "tb-01", "ingestion_timestamp": "2026-11-24T12:00:00Z"},
            "records": [
                {
                    "sensor_id": "PUN_SNS_001",
                    "zone_id": "ZONE_TEST_A",
                    "road_name": "Alpha Expressway",
                    "timestamp": "2026-11-24T12:30:00Z",
                    "vehicle_count": 60,
                    "average_speed": 45.0,
                    "road_occupancy": 40.0,
                    "congestion_level": "MODERATE",
                    "data_source_mode": "SIMULATED",
                }
            ],
        }
        with open(raw_t_dir / "traffic_batch_tb-01.json", "w", encoding="utf-8") as f:
            json.dump(t_batch, f)

        orchestrator = ProcessingPipelineOrchestrator(base_data_dir=base_dir)
        orchestrator.enricher.zones_config_path = sample_zones_config
        orchestrator.enricher.zone_metadata = orchestrator.enricher._load_zone_metadata()

        # Run pipeline for all layers
        results = orchestrator.run_pipeline(target_date=date_str, layer="all")
        assert len(results) == 3

        # Check all succeeded
        for res in results:
            assert res["status"] == "SUCCESS"

        # Check Silver files exist
        silver_w = base_dir / "processed" / "weather" / f"date={date_str}" / "weather_silver.parquet"
        silver_t = base_dir / "processed" / "traffic" / f"date={date_str}" / "traffic_silver.parquet"
        assert silver_w.exists()
        assert silver_t.exists()

        # Check Gold files exist
        gold_fact = base_dir / "curated" / "fact_traffic_weather_hourly" / f"date={date_str}" / "fact_traffic_weather.parquet"
        gold_agg = base_dir / "curated" / "agg_zone_mobility_kpis" / f"date={date_str}" / "zone_kpis.parquet"
        assert gold_fact.exists()
        assert gold_agg.exists()

        # Check manifest recorded
        manifest_file = base_dir / "processed" / "_processing_manifest.jsonl"
        assert manifest_file.exists()
        lines = manifest_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
