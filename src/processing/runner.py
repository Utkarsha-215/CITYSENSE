"""
CITYSENSE Platform - Data Transformation Pipeline Orchestrator & CLI Runner
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.processing.enricher import SpatioTemporalEnricher
from src.processing.traffic_transformer import TrafficTransformer
from src.processing.weather_transformer import WeatherTransformer
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_current_date_str, get_utc_now


class ProcessingPipelineOrchestrator:
    """
    Coordinates execution of Medallion transformations:
    Raw (Bronze) -> Processed (Silver) -> Curated (Gold).
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.processing.orchestrator", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

        self.weather_transformer = WeatherTransformer(self.base_data_dir, event_logger=self.logger)
        self.traffic_transformer = TrafficTransformer(self.base_data_dir, event_logger=self.logger)
        self.enricher = SpatioTemporalEnricher(self.base_data_dir, event_logger=self.logger)
        self.manifest_path = self.base_data_dir / "processed" / "_processing_manifest.jsonl"

    def _append_manifest(self, record: Dict[str, Any]):
        """Append processing audit entry to manifest JSONL."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        record["processed_at"] = get_utc_now().isoformat()
        with open(self.manifest_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def discover_raw_dates(self) -> List[str]:
        """Find all available date partition folders across raw traffic and weather directories."""
        dates = set()
        for sub in ("traffic", "weather"):
            raw_sub = self.base_data_dir / "raw" / sub
            if raw_sub.exists():
                for p in raw_sub.iterdir():
                    if p.is_dir() and len(p.name) == 10 and p.name[4] == "-" and p.name[7] == "-":
                        dates.add(p.name)
        return sorted(list(dates))

    def run_pipeline(
        self,
        target_date: Optional[str] = None,
        layer: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Execute transformation pipeline for target_date.
        Layers: 'silver', 'gold', 'all'.
        """
        date_str = target_date or get_current_date_str()
        results: List[Dict[str, Any]] = []

        self.logger.log_event(
            event_name="PIPELINE_STARTED",
            message=f"Starting processing pipeline for date {date_str} (layer={layer})",
            level="INFO",
            target_date=date_str,
            layer=layer,
        )

        # Silver Layer (Bronze-to-Silver)
        if layer in ("silver", "all"):
            # 1. Weather Transformer
            weather_res = self.weather_transformer.transform_partition(date_str)
            self._append_manifest(weather_res)
            results.append(weather_res)

            # 2. Traffic Transformer
            traffic_res = self.traffic_transformer.transform_partition(date_str)
            self._append_manifest(traffic_res)
            results.append(traffic_res)

        # Gold Layer (Silver-to-Gold)
        if layer in ("gold", "all"):
            enrich_res = self.enricher.enrich_partition(date_str)
            self._append_manifest(enrich_res)
            results.append(enrich_res)

        self.logger.log_event(
            event_name="PIPELINE_COMPLETED",
            message=f"Processing pipeline completed for date {date_str}: {len(results)} stages executed",
            level="INFO",
            target_date=date_str,
        )
        return results


def main():
    """CLI Entrypoint for CITYSENSE Processing Pipeline."""
    parser = argparse.ArgumentParser(
        prog="citysense-transform",
        description="CITYSENSE Medallion Data Transformation Engine (Milestone 2)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date partition to process in YYYY-MM-DD format (defaults to current date)",
    )
    parser.add_argument(
        "--layer",
        choices=["silver", "gold", "all"],
        default="all",
        help="Target processing layer to execute (default: all)",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Discover and process all available date partitions in raw storage",
    )

    args = parser.parse_args()
    orchestrator = ProcessingPipelineOrchestrator()

    print("\n" + "=" * 65)
    print("  CITYSENSE: Medallion Processing & Curation Engine (Milestone 2)")
    print("=" * 65)

    if args.all_dates:
        dates_to_run = orchestrator.discover_raw_dates()
        if not dates_to_run:
            print("[!] No date partitions discovered in data/raw/.")
            return
        print(f"[+] Discovered {len(dates_to_run)} date partition(s): {', '.join(dates_to_run)}")
    else:
        dates_to_run = [args.date or get_current_date_str()]

    for d in dates_to_run:
        print(f"\n--- Processing Partition: {d} (Layer: {args.layer}) ---")
        try:
            results = orchestrator.run_pipeline(target_date=d, layer=args.layer)
            for res in results:
                status = res.get("status", "UNKNOWN")
                src = res.get("source", "STAGE")
                lyr = res.get("layer", "")
                if status == "SUCCESS":
                    if lyr == "SILVER":
                        print(f"  [✓] {src} -> SILVER: {res.get('silver_records_count')} records written (dropped {res.get('duplicates_dropped')} dups)")
                    elif lyr == "GOLD":
                        print(f"  [✓] {src} -> GOLD: {res.get('fact_records_count')} fact records, {res.get('agg_records_count')} zone KPI records")
                else:
                    print(f"  [-] {src} -> {status}: {res.get('message', '')}")
        except Exception as e:
            print(f"  [!] Error processing {d}: {e}", file=sys.stderr)

    print("\n" + "=" * 65)
    print("  Processing Pipeline Execution Complete.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
