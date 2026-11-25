"""
CITYSENSE Platform - Raw Storage & Metadata Manifest Manager
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.utils.exceptions import BatchAlreadyExistsError, StorageError
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_current_date_str, get_utc_iso_string


class RawStorageManager:
    """
    Manages immutable date-partitioned JSON file persistence for raw data batches.
    Maintains append-only audit manifest with SHA256 cryptographic checksums.
    """

    def __init__(
        self,
        base_data_dir: Optional[Path] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_data_dir = base_data_dir or settings.DATA_DIR
        self.raw_dir = self.base_data_dir / "raw"
        self.manifest_path = self.raw_dir / "ingestion_manifest.jsonl"

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.storage", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

    def _compute_sha256(self, content_str: str) -> str:
        """Calculate SHA-256 hash of serialized content for audit trail."""
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    def _append_to_manifest(self, metadata: Dict[str, Any]):
        """Append an atomic batch record to the ingestion manifest JSONL file."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_line = json.dumps(metadata, default=str) + "\n"
        try:
            with open(self.manifest_path, "a", encoding="utf-8") as f:
                f.write(manifest_line)
        except Exception as e:
            raise StorageError(f"Failed to append to ingestion manifest: {e}") from e

    def save_batch(
        self,
        source_name: str,
        batch_id: str,
        data: Dict[str, Any],
        partition_date: Optional[str] = None,
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a raw batch to disk in an immutable date-partitioned directory.

        Directory structure:
        data/raw/{source_or_subfolder}/{YYYY-MM-DD}/{source_prefix}_batch_{batch_id}.json

        Returns:
            Dict containing batch manifest metadata.
        """
        date_partition = partition_date or get_current_date_str()
        target_subfolder = subfolder or source_name.lower().replace("_api", "").replace("_simulator", "")

        target_dir = self.raw_dir / target_subfolder / date_partition
        target_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{target_subfolder}_batch_{batch_id}.json"
        target_file = target_dir / file_name

        # Enforce immutability: never overwrite an existing batch
        if target_file.exists():
            err_msg = f"Batch file already exists at {target_file}. Overwriting raw batches is strictly prohibited."
            self.logger.failed_request(source_name=source_name, error=err_msg, batch_id=batch_id)
            raise BatchAlreadyExistsError(err_msg)

        # Serialize payload
        try:
            serialized_data = json.dumps(data, indent=2, default=str)
        except Exception as e:
            raise StorageError(f"Failed to serialize batch data to JSON: {e}") from e

        # Write to disk
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(serialized_data)
        except Exception as e:
            raise StorageError(f"Failed to write batch file to {target_file}: {e}") from e

        file_size_bytes = target_file.stat().st_size
        sha256_hash = self._compute_sha256(serialized_data)

        # Determine record count from payload
        if "records" in data and isinstance(data["records"], list):
            record_count = len(data["records"])
        elif "raw_payload" in data and isinstance(data["raw_payload"], dict):
            hourly = data["raw_payload"].get("hourly", {})
            record_count = len(hourly.get("time", []))
        else:
            record_count = 1

        batch_metadata: Dict[str, Any] = {
            "batch_id": batch_id,
            "source_name": source_name,
            "ingestion_timestamp": get_utc_iso_string(),
            "partition_date": date_partition,
            "record_count": record_count,
            "ingestion_status": "SUCCESS",
            "file_path": str(target_file),
            "file_name": file_name,
            "file_size_bytes": file_size_bytes,
            "sha256_checksum": sha256_hash,
        }

        # Append to manifest
        self._append_to_manifest(batch_metadata)

        self.logger.records_saved(
            source_name=source_name,
            file_path=str(target_file),
            record_count=record_count,
            batch_id=batch_id,
            file_size_bytes=file_size_bytes,
        )

        return batch_metadata

    def save_rejected_records(
        self,
        source_name: str,
        batch_id: str,
        rejected_records: List[Dict[str, Any]],
        partition_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Quarantine invalid / rejected records to data/raw/rejected/{YYYY-MM-DD}/.
        """
        if not rejected_records:
            return None

        date_partition = partition_date or get_current_date_str()
        rejected_dir = self.raw_dir / "rejected" / date_partition
        rejected_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"rejected_{source_name.lower()}_batch_{batch_id}.json"
        target_file = rejected_dir / file_name

        payload = {
            "metadata": {
                "batch_id": batch_id,
                "source_name": source_name,
                "rejected_timestamp": get_utc_iso_string(),
                "partition_date": date_partition,
                "rejected_count": len(rejected_records),
                "status": "QUARANTINED",
            },
            "rejected_records": rejected_records,
        }

        serialized = json.dumps(payload, indent=2, default=str)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(serialized)

        manifest_record = {
            "batch_id": batch_id,
            "source_name": f"{source_name}_REJECTED",
            "ingestion_timestamp": get_utc_iso_string(),
            "partition_date": date_partition,
            "record_count": len(rejected_records),
            "ingestion_status": "QUARANTINED",
            "file_path": str(target_file),
            "file_name": file_name,
            "file_size_bytes": target_file.stat().st_size,
            "sha256_checksum": self._compute_sha256(serialized),
        }
        self._append_to_manifest(manifest_record)

        self.logger.records_saved(
            source_name=f"{source_name}_REJECTED",
            file_path=str(target_file),
            record_count=len(rejected_records),
            batch_id=batch_id,
        )
        return manifest_record
