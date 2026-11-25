"""
CITYSENSE Platform - Parquet Data Access & Analytics Services
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from config.settings import settings
from src.utils.time_utils import get_current_date_str, get_utc_now


class DataService:
    """
    Columnar query service scanning Parquet and manifest files directly with zero database overhead.
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        zones_config_path: Optional[Path] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        self.zones_config_path = zones_config_path or settings.TRAFFIC_ZONES_CONFIG
        self.curated_dir = self.base_data_dir / "curated"
        self.processed_dir = self.base_data_dir / "processed"
        self.raw_dir = self.base_data_dir / "raw"
        self.zone_map = self._load_zone_map()

    def _load_zone_map(self) -> Dict[str, str]:
        """Map zone_id to human-readable zone_name."""
        if not self.zones_config_path.exists():
            return {}
        try:
            with open(self.zones_config_path, "r", encoding="utf-8") as f:
                zones = json.load(f)
            return {z["zone_id"]: z.get("zone_name", z["zone_id"]) for z in zones}
        except Exception:
            return {}

    def discover_dates(self) -> List[str]:
        """Find all available curated/raw date partition strings."""
        dates = set()
        # Scan curated fact table
        fact_dir = self.curated_dir / "fact_traffic_weather_hourly"
        if fact_dir.exists():
            for p in fact_dir.iterdir():
                if p.is_dir() and p.name.startswith("date="):
                    dates.add(p.name.replace("date=", ""))

        # Scan raw traffic
        raw_traffic = self.raw_dir / "traffic"
        if raw_traffic.exists():
            for p in raw_traffic.iterdir():
                if p.is_dir() and len(p.name) == 10 and p.name[4] == "-":
                    dates.add(p.name)

        return sorted(list(dates), reverse=True)

    def get_health_status(self) -> Dict[str, Any]:
        """Return system health, environment, and available partitions."""
        dates = self.discover_dates()
        manifest_path = self.raw_dir / "ingestion_manifest.jsonl"
        manifest_count = 0
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_count = sum(1 for line in f if line.strip())

        return {
            "status": "HEALTHY",
            "environment": settings.CITYSENSE_ENV,
            "timestamp": get_utc_now().isoformat(),
            "available_dates": dates,
            "total_raw_manifest_batches": manifest_count,
        }

    def get_zone_summaries(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return aggregated mobility summaries across all zones for a date."""
        target_date = date or (self.discover_dates()[0] if self.discover_dates() else get_current_date_str())
        agg_file = self.curated_dir / "agg_zone_mobility_kpis" / f"date={target_date}" / "zone_kpis.parquet"

        if not agg_file.exists():
            return []

        df = pd.read_parquet(agg_file)
        if df.empty:
            return []

        summaries = []
        for zone_id, group in df.groupby("zone_id"):
            zone_name = self.zone_map.get(zone_id, zone_id)
            summaries.append({
                "zone_id": str(zone_id),
                "zone_name": zone_name,
                "total_volume": int(group["total_vehicle_volume"].sum()),
                "avg_speed_kmh": round(float(group["avg_speed_kmh"].mean()), 1),
                "avg_occupancy_pct": round(float(group["avg_occupancy_pct"].mean()), 1),
                "avg_congestion_score": round(float(group["avg_congestion_score"].mean()), 1),
                "peak_congestion_score": round(float(group["peak_congestion_score"].max()), 1),
                "weather_disrupted_events": int(group["weather_disrupted_events"].sum()),
                "sensor_count": int(group["sensor_count"].max()),
            })

        return sorted(summaries, key=lambda x: x["avg_congestion_score"], reverse=True)

    def get_zone_kpis(self, zone_id: str, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return hourly KPI timeseries for a specific zone."""
        target_date = date or (self.discover_dates()[0] if self.discover_dates() else get_current_date_str())
        agg_file = self.curated_dir / "agg_zone_mobility_kpis" / f"date={target_date}" / "zone_kpis.parquet"

        if not agg_file.exists():
            return []

        df = pd.read_parquet(agg_file)
        if df.empty:
            return []

        df_zone = df[df["zone_id"] == zone_id].sort_values(by="observation_hour")
        if df_zone.empty:
            return []

        results = []
        for _, row in df_zone.iterrows():
            obs_hour = row["observation_hour"]
            obs_str = obs_hour.isoformat() if hasattr(obs_hour, "isoformat") else str(obs_hour)
            results.append({
                "zone_id": str(row["zone_id"]),
                "observation_hour": obs_str,
                "total_vehicle_volume": int(row["total_vehicle_volume"]),
                "avg_speed_kmh": round(float(row["avg_speed_kmh"]), 1),
                "avg_occupancy_pct": round(float(row["avg_occupancy_pct"]), 1),
                "avg_congestion_score": round(float(row["avg_congestion_score"]), 1),
                "peak_congestion_score": round(float(row["peak_congestion_score"]), 1),
                "avg_rainfall_mm": round(float(row.get("avg_rainfall_mm", 0.0)), 2),
                "weather_disrupted_events": int(row.get("weather_disrupted_events", 0)),
                "sensor_count": int(row["sensor_count"]),
            })
        return results

    def get_corridor_rankings(self, date: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Return top congested road corridors ranked by congestion score."""
        target_date = date or (self.discover_dates()[0] if self.discover_dates() else get_current_date_str())
        fact_file = self.curated_dir / "fact_traffic_weather_hourly" / f"date={target_date}" / "fact_traffic_weather.parquet"

        if not fact_file.exists():
            return []

        df = pd.read_parquet(fact_file)
        if df.empty:
            return []

        # Sort by congestion score descending
        df_sorted = df.sort_values(by="congestion_score", ascending=False).head(limit)
        results = []
        for _, row in df_sorted.iterrows():
            results.append({
                "sensor_id": str(row["sensor_id"]),
                "zone_id": str(row["zone_id"]),
                "road_name": str(row["road_name"]),
                "speed_limit_kmh": round(float(row["speed_limit_kmh"]), 1),
                "average_speed_kmh": round(float(row["average_speed_kmh"]), 1),
                "speed_deficit_ratio": round(float(row["speed_deficit_ratio"]), 2),
                "road_occupancy_pct": round(float(row["road_occupancy_pct"]), 1),
                "congestion_score": round(float(row["congestion_score"]), 1),
                "congestion_level": str(row["congestion_level"]),
                "is_weather_disrupted": bool(row.get("is_weather_disrupted", False)),
                "vehicle_count": int(row["vehicle_count"]),
            })
        return results

    def get_weather_impact_analysis(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Quantify speed degradation under adverse vs normal weather."""
        target_date = date or (self.discover_dates()[0] if self.discover_dates() else get_current_date_str())
        fact_file = self.curated_dir / "fact_traffic_weather_hourly" / f"date={target_date}" / "fact_traffic_weather.parquet"

        if not fact_file.exists():
            return {
                "date": target_date,
                "normal_conditions": {"sample_count": 0, "avg_speed_kmh": 0.0, "avg_occupancy_pct": 0.0, "avg_congestion_score": 0.0},
                "disrupted_conditions": {"sample_count": 0, "avg_speed_kmh": 0.0, "avg_occupancy_pct": 0.0, "avg_congestion_score": 0.0},
                "speed_reduction_pct": 0.0,
                "congestion_increase_pct": 0.0,
            }

        df = pd.read_parquet(fact_file)
        if df.empty:
            return {
                "date": target_date,
                "normal_conditions": {"sample_count": 0, "avg_speed_kmh": 0.0, "avg_occupancy_pct": 0.0, "avg_congestion_score": 0.0},
                "disrupted_conditions": {"sample_count": 0, "avg_speed_kmh": 0.0, "avg_occupancy_pct": 0.0, "avg_congestion_score": 0.0},
                "speed_reduction_pct": 0.0,
                "congestion_increase_pct": 0.0,
            }

        df_normal = df[df["is_weather_disrupted"] == False]
        df_disrupted = df[df["is_weather_disrupted"] == True]

        normal_metrics = {
            "sample_count": len(df_normal),
            "avg_speed_kmh": round(float(df_normal["average_speed_kmh"].mean()), 1) if not df_normal.empty else 0.0,
            "avg_occupancy_pct": round(float(df_normal["road_occupancy_pct"].mean()), 1) if not df_normal.empty else 0.0,
            "avg_congestion_score": round(float(df_normal["congestion_score"].mean()), 1) if not df_normal.empty else 0.0,
        }

        disrupted_metrics = {
            "sample_count": len(df_disrupted),
            "avg_speed_kmh": round(float(df_disrupted["average_speed_kmh"].mean()), 1) if not df_disrupted.empty else 0.0,
            "avg_occupancy_pct": round(float(df_disrupted["road_occupancy_pct"].mean()), 1) if not df_disrupted.empty else 0.0,
            "avg_congestion_score": round(float(df_disrupted["congestion_score"].mean()), 1) if not df_disrupted.empty else 0.0,
        }

        # Calculate percentage differences
        speed_red = 0.0
        cong_inc = 0.0
        if normal_metrics["avg_speed_kmh"] > 0 and disrupted_metrics["avg_speed_kmh"] > 0:
            speed_red = round(((normal_metrics["avg_speed_kmh"] - disrupted_metrics["avg_speed_kmh"]) / normal_metrics["avg_speed_kmh"]) * 100.0, 1)

        if normal_metrics["avg_congestion_score"] > 0 and disrupted_metrics["avg_congestion_score"] > 0:
            cong_inc = round(((disrupted_metrics["avg_congestion_score"] - normal_metrics["avg_congestion_score"]) / normal_metrics["avg_congestion_score"]) * 100.0, 1)

        return {
            "date": target_date,
            "normal_conditions": normal_metrics,
            "disrupted_conditions": disrupted_metrics,
            "speed_reduction_pct": speed_red,
            "congestion_increase_pct": cong_inc,
        }

    def get_ingestion_manifest(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return raw ingestion batches from manifest."""
        manifest_path = self.raw_dir / "ingestion_manifest.jsonl"
        if not manifest_path.exists():
            return []

        records = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        return records[-limit:][::-1]

    def get_processing_manifest(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return processing batches from manifest."""
        manifest_path = self.processed_dir / "_processing_manifest.jsonl"
        if not manifest_path.exists():
            return []

        records = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        return records[-limit:][::-1]
