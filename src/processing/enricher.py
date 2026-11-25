"""
CITYSENSE Platform - Silver-to-Gold Spatiotemporal Enricher & Mobility KPI Engine
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from config.settings import settings
from src.utils.exceptions import CitySenseError
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_current_date_str, get_utc_now


class SpatioTemporalEnricher:
    """
    Performs spatiotemporal feature joins between Silver traffic and weather streams.
    Calculates smart city mobility indicators and outputs curated Gold analytical datasets.
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        zones_config_path: Optional[Path] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        self.processed_dir = self.base_data_dir / "processed"
        self.curated_dir = self.base_data_dir / "curated"
        self.zones_config_path = zones_config_path or settings.TRAFFIC_ZONES_CONFIG

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.enricher", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

        self.zone_metadata = self._load_zone_metadata()

    def _load_zone_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load zone metadata map from config/zones.json."""
        if not self.zones_config_path.exists():
            return {}
        try:
            with open(self.zones_config_path, "r", encoding="utf-8") as f:
                zones = json.load(f)
            return {z["zone_id"]: z for z in zones}
        except Exception:
            return {}

    def enrich_partition(self, partition_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Join Silver traffic and weather datasets for partition_date and calculate Gold analytics.
        """
        date_str = partition_date or get_current_date_str()
        traffic_path = self.processed_dir / "traffic" / f"date={date_str}" / "traffic_silver.parquet"
        weather_path = self.processed_dir / "weather" / f"date={date_str}" / "weather_silver.parquet"

        if not traffic_path.exists():
            return {
                "status": "SKIPPED",
                "message": f"Silver traffic data not found at {traffic_path}",
                "records_curated": 0,
            }

        # Read Silver traffic
        df_traffic = pd.read_parquet(traffic_path)
        if df_traffic.empty:
            return {"status": "EMPTY", "message": "Silver traffic dataset is empty", "records_curated": 0}

        # Read Silver weather (fallback to empty if not found)
        if weather_path.exists():
            df_weather = pd.read_parquet(weather_path)
        else:
            df_weather = pd.DataFrame(columns=[
                "timestamp", "city", "temperature_celsius", "relative_humidity_pct",
                "rainfall_mm", "wind_speed_kmh"
            ])

        # 1. Temporal alignment: floor traffic timestamp to nearest hour for join
        df_traffic["observation_hour"] = df_traffic["timestamp"].dt.floor("h")

        if not df_weather.empty:
            df_weather["observation_hour"] = df_weather["timestamp"].dt.floor("h")
            # Select relevant weather columns to avoid collision
            weather_cols = [
                "observation_hour", "temperature_celsius", "relative_humidity_pct",
                "rainfall_mm", "wind_speed_kmh"
            ]
            df_weather_subset = df_weather[weather_cols].drop_duplicates(subset=["observation_hour"])
            df_enriched = pd.merge(df_traffic, df_weather_subset, on="observation_hour", how="left")
        else:
            df_enriched = df_traffic.copy()
            df_enriched["temperature_celsius"] = np.nan
            df_enriched["relative_humidity_pct"] = np.nan
            df_enriched["rainfall_mm"] = 0.0
            df_enriched["wind_speed_kmh"] = 0.0

        # Fill missing weather attributes with neutral defaults
        df_enriched["rainfall_mm"] = df_enriched["rainfall_mm"].fillna(0.0)
        df_enriched["wind_speed_kmh"] = df_enriched["wind_speed_kmh"].fillna(0.0)

        # 2. Add zone speed limits and compute Mobility KPIs
        speed_limits = []
        for zone_id in df_enriched["zone_id"]:
            z_meta = self.zone_metadata.get(zone_id, {})
            speed_limits.append(float(z_meta.get("speed_limit_kmh", 50.0)))

        df_enriched["speed_limit_kmh"] = np.array(speed_limits, dtype="float32")

        # KPI 1: Speed Deficit Ratio
        speed_deficit = np.maximum(0.0, df_enriched["speed_limit_kmh"] - df_enriched["average_speed_kmh"])
        df_enriched["speed_deficit_ratio"] = np.round(speed_deficit / df_enriched["speed_limit_kmh"], 4).astype("float32")

        # KPI 2: Mobility Congestion Score (0.0 to 100.0)
        # Weighted composite: 50% occupancy + 50% speed reduction percentage
        congestion_score = 0.5 * df_enriched["road_occupancy_pct"] + 0.5 * (df_enriched["speed_deficit_ratio"] * 100.0)
        df_enriched["congestion_score"] = np.round(np.clip(congestion_score, 0.0, 100.0), 2).astype("float32")

        # KPI 3: Weather Disruption Flag (Rain > 1.0mm or Wind > 30km/h)
        df_enriched["is_weather_disrupted"] = (
            (df_enriched["rainfall_mm"] > 1.0) | (df_enriched["wind_speed_kmh"] > 30.0)
        ).astype(bool)

        # KPI 4: Estimated Corridor Throughput (vehicles/hour equivalent)
        speed_ratio = np.clip(df_enriched["average_speed_kmh"] / df_enriched["speed_limit_kmh"], 0.1, 1.2)
        df_enriched["estimated_hourly_throughput"] = (
            df_enriched["vehicle_count"] * speed_ratio
        ).round().astype("int32")

        # 3. Output Gold Fact Table: fact_traffic_weather_hourly
        fact_dir = self.curated_dir / "fact_traffic_weather_hourly" / f"date={date_str}"
        fact_dir.mkdir(parents=True, exist_ok=True)
        fact_file = fact_dir / "fact_traffic_weather.parquet"
        df_enriched.to_parquet(fact_file, engine="pyarrow", compression="snappy", index=False)

        # 4. Output Gold Aggregation Table: agg_zone_mobility_kpis
        agg_df = df_enriched.groupby(["zone_id", "observation_hour"]).agg(
            total_vehicle_volume=("vehicle_count", "sum"),
            avg_speed_kmh=("average_speed_kmh", "mean"),
            avg_occupancy_pct=("road_occupancy_pct", "mean"),
            avg_congestion_score=("congestion_score", "mean"),
            peak_congestion_score=("congestion_score", "max"),
            avg_rainfall_mm=("rainfall_mm", "mean"),
            weather_disrupted_events=("is_weather_disrupted", "sum"),
            sensor_count=("sensor_id", "nunique"),
        ).reset_index()

        agg_df["avg_speed_kmh"] = agg_df["avg_speed_kmh"].round(2).astype("float32")
        agg_df["avg_occupancy_pct"] = agg_df["avg_occupancy_pct"].round(2).astype("float32")
        agg_df["avg_congestion_score"] = agg_df["avg_congestion_score"].round(2).astype("float32")
        agg_df["peak_congestion_score"] = agg_df["peak_congestion_score"].round(2).astype("float32")
        agg_df["avg_rainfall_mm"] = agg_df["avg_rainfall_mm"].round(2).astype("float32")
        agg_df["total_vehicle_volume"] = agg_df["total_vehicle_volume"].astype("int32")
        agg_df["weather_disrupted_events"] = agg_df["weather_disrupted_events"].astype("int32")
        agg_df["sensor_count"] = agg_df["sensor_count"].astype("int32")

        agg_dir = self.curated_dir / "agg_zone_mobility_kpis" / f"date={date_str}"
        agg_dir.mkdir(parents=True, exist_ok=True)
        agg_file = agg_dir / "zone_kpis.parquet"
        agg_df.to_parquet(agg_file, engine="pyarrow", compression="snappy", index=False)

        metrics = {
            "source": "CROSS_DOMAIN_ENRICHER",
            "layer": "GOLD",
            "partition_date": date_str,
            "fact_records_count": len(df_enriched),
            "agg_records_count": len(agg_df),
            "fact_output_path": str(fact_file),
            "agg_output_path": str(agg_file),
            "status": "SUCCESS",
        }

        self.logger.log_event(
            event_name="CURATION_COMPLETED",
            message=f"Gold Curation completed: {len(df_enriched)} fact rows, {len(agg_df)} zone KPI aggregate rows",
            level="INFO",
            **metrics
        )
        return metrics
