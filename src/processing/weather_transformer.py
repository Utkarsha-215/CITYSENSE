"""
CITYSENSE Platform - Weather Data Transformer (Bronze-to-Silver)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from config.settings import settings
from src.utils.exceptions import CitySenseError
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_current_date_str, get_utc_now


class WeatherTransformer:
    """
    Cleanses, normalizes, and deduplicates raw Open-Meteo weather JSON batches
    into standardized columnar Parquet format (Silver layer).
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        self.raw_weather_dir = self.base_data_dir / "raw" / "weather"
        self.processed_weather_dir = self.base_data_dir / "processed" / "weather"

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.processing.weather", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

    def extract_raw_records_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract unrolled records from a single raw weather JSON batch file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        batch_id = metadata.get("batch_id", "unknown")
        city = metadata.get("city", "Pune")
        lat = metadata.get("latitude", 18.5204)
        lon = metadata.get("longitude", 73.8567)
        ingested_at = metadata.get("ingestion_timestamp", get_utc_now().isoformat())

        raw_payload = data.get("raw_payload", {})
        hourly = raw_payload.get("hourly", {})

        timestamps = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        rains = hourly.get("rain", [])
        winds = hourly.get("wind_speed_10m", [])

        records = []
        for i in range(len(timestamps)):
            records.append({
                "timestamp": timestamps[i],
                "city": city,
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
                "temperature_celsius": float(temps[i]) if i < len(temps) and temps[i] is not None else None,
                "relative_humidity_pct": float(humidities[i]) if i < len(humidities) and humidities[i] is not None else None,
                "rainfall_mm": float(rains[i]) if i < len(rains) and rains[i] is not None else None,
                "wind_speed_kmh": float(winds[i]) if i < len(winds) and winds[i] is not None else None,
                "source_batch_id": batch_id,
                "ingested_at": ingested_at,
            })
        return records

    def transform_partition(self, partition_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Process all raw weather batches for a given partition date, deduplicate,
        and write Silver Parquet dataset.
        """
        date_str = partition_date or get_current_date_str()
        target_raw_dir = self.raw_weather_dir / date_str

        if not target_raw_dir.exists():
            return {
                "status": "SKIPPED",
                "message": f"No raw weather directory found for date {date_str}",
                "records_processed": 0,
            }

        batch_files = list(target_raw_dir.glob("weather_batch_*.json"))
        if not batch_files:
            return {
                "status": "SKIPPED",
                "message": f"No weather batch JSON files found in {target_raw_dir}",
                "records_processed": 0,
            }

        all_records = []
        for bf in batch_files:
            all_records.extend(self.extract_raw_records_from_file(bf))

        if not all_records:
            return {
                "status": "EMPTY",
                "message": f"Raw files contained 0 records",
                "records_processed": 0,
            }

        raw_count = len(all_records)
        df = pd.DataFrame(all_records)

        # 1. Cast timestamps to UTC datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True)

        # 2. Schema type casting
        df["city"] = df["city"].astype("string")
        df["latitude"] = df["latitude"].astype("float32")
        df["longitude"] = df["longitude"].astype("float32")
        df["temperature_celsius"] = df["temperature_celsius"].astype("float32")
        df["relative_humidity_pct"] = df["relative_humidity_pct"].astype("float32")
        df["rainfall_mm"] = df["rainfall_mm"].astype("float32")
        df["wind_speed_kmh"] = df["wind_speed_kmh"].astype("float32")
        df["source_batch_id"] = df["source_batch_id"].astype("string")

        # 3. Deduplication on natural key (city, timestamp), keeping latest ingested_at
        df = df.sort_values(by=["city", "timestamp", "ingested_at"])
        deduped_df = df.drop_duplicates(subset=["city", "timestamp"], keep="last").reset_index(drop=True)
        dropped_count = raw_count - len(deduped_df)

        # 4. Save to date-partitioned Parquet (Silver)
        out_dir = self.processed_weather_dir / f"date={date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "weather_silver.parquet"

        deduped_df.to_parquet(out_file, engine="pyarrow", compression="snappy", index=False)

        metrics = {
            "source": "WEATHER",
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
            message=f"Weather Bronze-to-Silver completed: {len(deduped_df)} records saved ({dropped_count} duplicates dropped)",
            level="INFO",
            **metrics
        )
        return metrics
