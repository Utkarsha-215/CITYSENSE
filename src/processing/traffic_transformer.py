"""
CITYSENSE Platform - Traffic Data Transformer (Bronze-to-Silver)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from config.settings import settings
from src.utils.exceptions import CitySenseError
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_current_date_str, get_utc_now


class TrafficTransformer:
    """
    Cleanses, normalizes, casts, and deduplicates raw traffic sensor JSON batches
    into standardized columnar Parquet format (Silver layer).
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        self.raw_traffic_dir = self.base_data_dir / "raw" / "traffic"
        self.processed_traffic_dir = self.base_data_dir / "processed" / "traffic"

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.processing.traffic", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

    def extract_raw_records_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract sensor observation rows from a single raw traffic JSON batch file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        batch_id = metadata.get("batch_id", "unknown")
        ingested_at = metadata.get("ingestion_timestamp", get_utc_now().isoformat())
        records = data.get("records", [])

        row_list = []
        for r in records:
            row = dict(r)
            row["source_batch_id"] = batch_id
            row["ingested_at"] = ingested_at
            row_list.append(row)
        return row_list

    def transform_partition(self, partition_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Process all raw traffic batches for a given partition date, deduplicate,
        and write Silver Parquet dataset.
        """
        date_str = partition_date or get_current_date_str()
        target_raw_dir = self.raw_traffic_dir / date_str

        if not target_raw_dir.exists():
            return {
                "status": "SKIPPED",
                "message": f"No raw traffic directory found for date {date_str}",
                "records_processed": 0,
            }

        batch_files = list(target_raw_dir.glob("traffic_batch_*.json"))
        if not batch_files:
            return {
                "status": "SKIPPED",
                "message": f"No traffic batch JSON files found in {target_raw_dir}",
                "records_processed": 0,
            }

        all_records = []
        for bf in batch_files:
            all_records.extend(self.extract_raw_records_from_file(bf))

        if not all_records:
            return {
                "status": "EMPTY",
                "message": "Raw files contained 0 records",
                "records_processed": 0,
            }

        raw_count = len(all_records)
        df = pd.DataFrame(all_records)

        # 1. Cast timestamps to UTC datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True)

        # 2. Schema type casting & normalization
        df["sensor_id"] = df["sensor_id"].astype("string")
        df["zone_id"] = df["zone_id"].astype("string")
        df["road_name"] = df["road_name"].astype("string")
        df["vehicle_count"] = pd.to_numeric(df["vehicle_count"], errors="coerce").fillna(0).astype("int32")
        df["average_speed_kmh"] = pd.to_numeric(df["average_speed"], errors="coerce").astype("float32")
        df["road_occupancy_pct"] = pd.to_numeric(df["road_occupancy"], errors="coerce").astype("float32")
        df["congestion_level"] = df["congestion_level"].astype("string")
        df["data_source_mode"] = df.get("data_source_mode", "SIMULATED").astype("string")
        df["source_batch_id"] = df["source_batch_id"].astype("string")

        # Keep only required standardized columns
        keep_cols = [
            "sensor_id",
            "zone_id",
            "road_name",
            "timestamp",
            "vehicle_count",
            "average_speed_kmh",
            "road_occupancy_pct",
            "congestion_level",
            "data_source_mode",
            "source_batch_id",
            "ingested_at",
        ]
        df = df[[c for c in keep_cols if c in df.columns]]

        # 3. Deduplication on natural key (sensor_id, timestamp), keeping latest ingested_at
        df = df.sort_values(by=["sensor_id", "timestamp", "ingested_at"])
        deduped_df = df.drop_duplicates(subset=["sensor_id", "timestamp"], keep="last").reset_index(drop=True)
        dropped_count = raw_count - len(deduped_df)

        # 4. Save to date-partitioned Parquet (Silver)
        out_dir = self.processed_traffic_dir / f"date={date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "traffic_silver.parquet"

        deduped_df.to_parquet(out_file, engine="pyarrow", compression="snappy", index=False)

        metrics = {
            "source": "TRAFFIC",
            "layer": "SILVER",
            "partition_date": date_str,
            "raw_records_count": raw_count,
            "silver_records_count": len(deduped_df),
            "duplicates_dropped": dropped_count,
            "output_path": str(out_file),
            "status": "SUCCESS",
        }

        self.logger.log_event(
            event_name="TRANSFORMATION_COMPLETED",
            message=f"Traffic Bronze-to-Silver completed: {len(deduped_df)} records saved ({dropped_count} duplicates dropped)",
            level="INFO",
            **metrics
        )
        return metrics
