"""
CITYSENSE Platform - Ingestion Pipeline Orchestrator & CLI Runner
"""

import argparse
import sys
import uuid
from typing import Any, Dict, Optional

from config.settings import settings
from src.ingestion.traffic_simulator import TrafficSensorSimulator
from src.ingestion.weather_client import WeatherIngestionClient
from src.quality.traffic_validator import TrafficDataValidator
from src.quality.weather_validator import WeatherDataValidator
from src.storage.raw_storage import RawStorageManager
from src.utils.logger import StructuredEventLogger, setup_logger


class IngestionOrchestrator:
    """
    Coordinates end-to-end ingestion lifecycle across all smart city data streams:
    Extract -> Validate -> Store Raw & Quarantine -> Manifest Tracking.
    """

    def __init__(
        self,
        storage_manager: Optional[RawStorageManager] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.orchestrator", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

        self.storage = storage_manager or RawStorageManager(event_logger=self.logger)
        self.weather_validator = WeatherDataValidator(event_logger=self.logger)
        self.traffic_validator = TrafficDataValidator(event_logger=self.logger)

    def run_weather_ingestion(
        self,
        city_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute weather ingestion workflow:
        1. Query Open-Meteo API
        2. Validate hourly atmospheric observations
        3. Persist raw response envelope
        4. Quarantine any invalid records
        """
        batch_id = batch_id or str(uuid.uuid4())
        client = WeatherIngestionClient(
            city_name=city_name,
            latitude=latitude,
            longitude=longitude,
            event_logger=self.logger,
        )

        # 1. Fetch raw payload
        envelope = client.fetch_weather_data(batch_id=batch_id)

        # 2. Extract records for validation
        unrolled_records = WeatherIngestionClient.unroll_hourly_records(envelope)
        val_result = self.weather_validator.validate_records(unrolled_records)

        # 3. Store raw batch
        batch_manifest = self.storage.save_batch(
            source_name="WEATHER",
            batch_id=batch_id,
            data=envelope,
            subfolder="weather",
        )

        # 4. Quarantine rejected records if any exist
        rejected_manifest = None
        if val_result.rejected_records:
            rejected_manifest = self.storage.save_rejected_records(
                source_name="WEATHER",
                batch_id=batch_id,
                rejected_records=val_result.rejected_records,
            )

        return {
            "source": "WEATHER",
            "batch_id": batch_id,
            "status": "SUCCESS",
            "total_extracted": len(unrolled_records),
            "valid_records": val_result.valid_count,
            "rejected_records": val_result.rejected_count,
            "batch_manifest": batch_manifest,
            "rejected_manifest": rejected_manifest,
        }

    def run_traffic_ingestion(
        self,
        num_records: int = 25,
        seed: Optional[int] = None,
        batch_id: Optional[str] = None,
        inject_anomalies: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute traffic simulator ingestion workflow:
        1. Generate synthetic sensor observations
        2. Inject test anomalies (if requested)
        3. Validate schema and domain constraints
        4. Persist valid records to raw traffic storage
        5. Quarantine invalid records to raw rejected storage
        """
        batch_id = batch_id or str(uuid.uuid4())
        simulator = TrafficSensorSimulator(
            num_sensors=num_records,
            default_seed=seed,
            event_logger=self.logger,
        )

        # 1. Generate batch
        batch_envelope = simulator.generate_batch(
            num_records=num_records,
            seed=seed,
            batch_id=batch_id,
        )
        raw_records = list(batch_envelope["records"])

        # 2. Optional anomaly injection for validation demonstrations
        if inject_anomalies:
            raw_records.extend([
                {
                    "sensor_id": "",  # Missing sensor ID
                    "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
                    "road_name": "FC Road",
                    "timestamp": "2026-11-24T16:00:00Z",
                    "vehicle_count": 50,
                    "average_speed": 40.0,
                    "road_occupancy": 35.0,
                    "congestion_level": "LOW",
                    "data_source_mode": "SIMULATED",
                },
                {
                    "sensor_id": "PUN_SNS_998",
                    "zone_id": "ZONE_IT_HINJEWADI",
                    "road_name": "Hinjewadi Phase 1 Main Rd",
                    "timestamp": "2026-11-24T16:00:00Z",
                    "vehicle_count": -10,  # Negative vehicle count
                    "average_speed": -5.0,  # Negative speed
                    "road_occupancy": 150.0,  # Occupancy > 100%
                    "congestion_level": "SEVERE",
                    "data_source_mode": "SIMULATED",
                },
            ])

        # 3. Quality validation
        val_result = self.traffic_validator.validate_records(raw_records)

        # 4. Save valid batch envelope
        valid_envelope = {
            "metadata": {
                **batch_envelope["metadata"],
                "valid_record_count": val_result.valid_count,
                "rejected_record_count": val_result.rejected_count,
            },
            "records": val_result.valid_records,
        }

        batch_manifest = self.storage.save_batch(
            source_name="TRAFFIC",
            batch_id=batch_id,
            data=valid_envelope,
            subfolder="traffic",
        )

        # 5. Quarantine rejected records
        rejected_manifest = None
        if val_result.rejected_records:
            rejected_manifest = self.storage.save_rejected_records(
                source_name="TRAFFIC",
                batch_id=batch_id,
                rejected_records=val_result.rejected_records,
            )

        return {
            "source": "TRAFFIC",
            "batch_id": batch_id,
            "status": "SUCCESS",
            "total_extracted": len(raw_records),
            "valid_records": val_result.valid_count,
            "rejected_records": val_result.rejected_count,
            "batch_manifest": batch_manifest,
            "rejected_manifest": rejected_manifest,
        }


def main():
    """CLI entrypoint for CITYSENSE Ingestion Runner."""
    parser = argparse.ArgumentParser(
        prog="citysense-ingest",
        description="CITYSENSE Smart City Ingestion Engine (Milestone 1)",
    )
    parser.add_argument(
        "--source",
        choices=["weather", "traffic", "both"],
        default="both",
        help="Data source to ingest (default: both)",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=25,
        help="Number of traffic sensor records to simulate (default: 25)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for traffic reproducibility (default: 42)",
    )
    parser.add_argument(
        "--city",
        type=str,
        default="Pune",
        help="City name for weather forecast (default: Pune)",
    )
    parser.add_argument(
        "--simulate-anomalies",
        action="store_true",
        help="Inject intentional invalid records to verify quality quarantine handling",
    )

    args = parser.parse_args()
    orchestrator = IngestionOrchestrator()

    print("\n" + "=" * 60)
    print("  CITYSENSE: Smart City Multi-Source Ingestion Engine")
    print("=" * 60)

    results = []

    if args.source in ("weather", "both"):
        print(f"\n[+] Ingesting Meteorological Data for {args.city}...")
        try:
            weather_res = orchestrator.run_weather_ingestion(city_name=args.city)
            print(f"    Status: SUCCESS | Batch ID: {weather_res['batch_id']}")
            print(f"    Extracted: {weather_res['total_extracted']} hourly records")
            print(f"    Valid: {weather_res['valid_records']} | Rejected: {weather_res['rejected_records']}")
            print(f"    Output Path: {weather_res['batch_manifest']['file_path']}")
            results.append(weather_res)
        except Exception as e:
            print(f"    [!] Weather Ingestion Error: {e}", file=sys.stderr)

    if args.source in ("traffic", "both"):
        print(f"\n[+] Ingesting Traffic Sensor Stream ({args.records} sensors, seed={args.seed})...")
        try:
            traffic_res = orchestrator.run_traffic_ingestion(
                num_records=args.records,
                seed=args.seed,
                inject_anomalies=args.simulate_anomalies,
            )
            print(f"    Status: SUCCESS | Batch ID: {traffic_res['batch_id']}")
            print(f"    Generated: {traffic_res['total_extracted']} sensor records")
            print(f"    Valid: {traffic_res['valid_records']} | Quarantined: {traffic_res['rejected_records']}")
            print(f"    Output Path: {traffic_res['batch_manifest']['file_path']}")
            if traffic_res["rejected_manifest"]:
                print(f"    Quarantine Path: {traffic_res['rejected_manifest']['file_path']}")
            results.append(traffic_res)
        except Exception as e:
            print(f"    [!] Traffic Ingestion Error: {e}", file=sys.stderr)

    print("\n" + "=" * 60)
    print(f"  Ingestion Finished. Batches processed: {len(results)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
