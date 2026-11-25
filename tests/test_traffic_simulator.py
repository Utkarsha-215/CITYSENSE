"""
CITYSENSE Platform - Traffic Simulator Unit Tests
"""

from datetime import datetime, timezone
import pytest

from src.ingestion.traffic_simulator import TrafficSensorSimulator
from src.utils.exceptions import TrafficSimulatorError


class TestTrafficSensorSimulator:
    """Test suite for synthetic traffic sensor stream generation."""

    def test_record_generation_count(self, sample_zones_config):
        """Verify simulator generates the exact number of requested records."""
        sim = TrafficSensorSimulator(zones_config_path=sample_zones_config, num_sensors=10)
        batch = sim.generate_batch(num_records=15)

        assert len(batch["records"]) == 15
        assert batch["metadata"]["record_count"] == 15
        assert batch["metadata"]["data_source_mode"] == "SIMULATED"

    def test_seed_reproducibility(self, sample_zones_config):
        """Verify identical seeds produce byte-for-byte identical record attributes."""
        sim = TrafficSensorSimulator(zones_config_path=sample_zones_config)
        fixed_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        batch_1 = sim.generate_batch(num_records=10, seed=12345, start_time=fixed_time)
        batch_2 = sim.generate_batch(num_records=10, seed=12345, start_time=fixed_time)

        assert batch_1["records"] == batch_2["records"]

    def test_seed_variance(self, sample_zones_config):
        """Verify distinct seeds produce different record values."""
        sim = TrafficSensorSimulator(zones_config_path=sample_zones_config)
        fixed_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

        batch_1 = sim.generate_batch(num_records=10, seed=111, start_time=fixed_time)
        batch_2 = sim.generate_batch(num_records=10, seed=222, start_time=fixed_time)

        assert batch_1["records"] != batch_2["records"]

    def test_required_schema_fields(self, sample_zones_config):
        """Verify each generated record contains all mandatory attributes."""
        sim = TrafficSensorSimulator(zones_config_path=sample_zones_config)
        batch = sim.generate_batch(num_records=5, seed=42)

        required_fields = {
            "sensor_id",
            "zone_id",
            "road_name",
            "timestamp",
            "vehicle_count",
            "average_speed",
            "road_occupancy",
            "congestion_level",
            "data_source_mode",
            "simulation_seed",
        }

        for record in batch["records"]:
            assert required_fields.issubset(record.keys())
            assert record["data_source_mode"] == "SIMULATED"
            assert record["sensor_id"].startswith("PUN_SNS_")
            assert record["congestion_level"] in ("LOW", "MODERATE", "HIGH", "SEVERE")

    def test_physical_boundary_ranges(self, sample_zones_config):
        """Verify generated records fall within realistic physical ranges."""
        sim = TrafficSensorSimulator(zones_config_path=sample_zones_config)
        batch = sim.generate_batch(num_records=50, seed=999)

        for record in batch["records"]:
            assert record["vehicle_count"] >= 0
            assert 0.0 <= record["road_occupancy"] <= 100.0
            assert 0.0 < record["average_speed"] <= 150.0

    def test_missing_zones_config_raises_error(self, tmp_path):
        """Verify missing zones configuration raises TrafficSimulatorError."""
        non_existent = tmp_path / "does_not_exist.json"
        with pytest.raises(TrafficSimulatorError):
            TrafficSensorSimulator(zones_config_path=non_existent)
