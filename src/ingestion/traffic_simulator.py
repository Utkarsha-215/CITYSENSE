"""
CITYSENSE Platform - Traffic Sensor Simulator
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.utils.exceptions import TrafficSimulatorError
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_utc_iso_string, get_utc_now


class TrafficSensorSimulator:
    """
    High-fidelity deterministic synthetic generator for smart city traffic sensor streams.
    Generates multi-zone traffic flows labeled with reproducibility seeds and SIMULATED flags.
    """

    def __init__(
        self,
        zones_config_path: Optional[Path] = None,
        num_sensors: Optional[int] = None,
        default_seed: Optional[int] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.zones_config_path = zones_config_path or settings.TRAFFIC_ZONES_CONFIG
        self.num_sensors = num_sensors or settings.TRAFFIC_NUM_SENSORS
        self.default_seed = default_seed if default_seed is not None else settings.TRAFFIC_DEFAULT_SEED

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.traffic_sim", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

        self.zones = self._load_zones_config()

    def _load_zones_config(self) -> List[Dict[str, Any]]:
        """Load zone metadata definitions from config/zones.json."""
        if not self.zones_config_path.exists():
            raise TrafficSimulatorError(f"Zones configuration file not found at: {self.zones_config_path}")

        try:
            with open(self.zones_config_path, "r", encoding="utf-8") as f:
                zones = json.load(f)
            if not isinstance(zones, list) or len(zones) == 0:
                raise TrafficSimulatorError("Zones configuration must contain a non-empty list of zone objects.")
            return zones
        except Exception as e:
            raise TrafficSimulatorError(f"Error loading zones config: {e}") from e

    def generate_batch(
        self,
        num_records: Optional[int] = None,
        seed: Optional[int] = None,
        batch_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate a batch of realistic simulated traffic records.

        Args:
            num_records: Number of sensor observation records to generate (defaults to self.num_sensors).
            seed: Reproducible random seed. If None, uses default_seed.
            batch_id: Explicit batch ID (or auto-generates a UUIDv4).
            start_time: Base reference datetime for timestamps (defaults to current UTC).

        Returns:
            Dict envelope containing batch metadata and list of records.
        """
        active_seed = seed if seed is not None else self.default_seed
        rng = random.Random(active_seed)
        count = num_records or self.num_sensors
        batch_id = batch_id or str(uuid.uuid4())
        ref_time = start_time or get_utc_now()

        self.logger.ingestion_started(
            source_name="TRAFFIC_SENSOR_SIMULATOR",
            batch_id=batch_id,
            num_records=count,
            seed=active_seed,
        )

        records: List[Dict[str, Any]] = []

        for i in range(count):
            zone = rng.choice(self.zones)
            zone_id = zone["zone_id"]
            road_name = rng.choice(zone["roads"])
            sensor_index = (i % self.num_sensors) + 1
            sensor_id = f"PUN_SNS_{sensor_index:03d}"

            # Simulate timestamp (jitter within past hour for realism)
            time_offset_seconds = rng.randint(0, 3600)
            record_time = ref_time - timedelta(seconds=time_offset_seconds)
            timestamp_str = record_time.isoformat()

            # Realistic mobility physics:
            # Capacity, vehicle count, occupancy, and average speed relationship
            base_capacity = zone.get("base_capacity", 150)
            speed_limit = zone.get("speed_limit_kmh", 50.0)

            # Rush hour weighting: between 8-11 AM and 5-8 PM local time
            hour = record_time.hour
            is_rush_hour = (8 <= hour <= 11) or (17 <= hour <= 20)
            traffic_density = rng.uniform(0.65, 0.98) if is_rush_hour else rng.uniform(0.15, 0.60)

            vehicle_count = int(round(base_capacity * traffic_density * rng.uniform(0.85, 1.15)))
            vehicle_count = max(0, vehicle_count)

            # Road occupancy percentage (0.0 to 100.0)
            road_occupancy = round(min(100.0, max(0.0, (vehicle_count / base_capacity) * 100.0 * rng.uniform(0.9, 1.05))), 2)

            # Speed calculation: high occupancy drops speed down to congestion crawl
            if road_occupancy > 85.0:
                average_speed = round(rng.uniform(5.0, 15.0), 2)
                congestion_level = "SEVERE"
            elif road_occupancy > 65.0:
                average_speed = round(rng.uniform(15.0, speed_limit * 0.55), 2)
                congestion_level = "HIGH"
            elif road_occupancy > 40.0:
                average_speed = round(rng.uniform(speed_limit * 0.55, speed_limit * 0.85), 2)
                congestion_level = "MODERATE"
            else:
                average_speed = round(rng.uniform(speed_limit * 0.85, speed_limit * 1.10), 2)
                congestion_level = "LOW"

            record: Dict[str, Any] = {
                "sensor_id": sensor_id,
                "zone_id": zone_id,
                "road_name": road_name,
                "timestamp": timestamp_str,
                "vehicle_count": vehicle_count,
                "average_speed": average_speed,
                "road_occupancy": road_occupancy,
                "congestion_level": congestion_level,
                "data_source_mode": "SIMULATED",
                "simulation_seed": active_seed,
            }
            records.append(record)

        self.logger.records_extracted(
            source_name="TRAFFIC_SENSOR_SIMULATOR",
            record_count=len(records),
            batch_id=batch_id,
        )

        envelope: Dict[str, Any] = {
            "metadata": {
                "batch_id": batch_id,
                "source_name": "TRAFFIC_SENSOR_SIMULATOR",
                "data_source_mode": "SIMULATED",
                "simulation_seed": active_seed,
                "ingestion_timestamp": get_utc_iso_string(),
                "record_count": len(records),
                "ingestion_status": "SUCCESS",
            },
            "records": records,
        }
        return envelope
