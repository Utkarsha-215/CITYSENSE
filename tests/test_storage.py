"""
CITYSENSE Platform - Storage Manager Unit Tests
"""

import json
from pathlib import Path
import pytest

from src.storage.raw_storage import RawStorageManager
from src.utils.exceptions import BatchAlreadyExistsError


class TestRawStorageManager:
    """Test suite for immutable date-partitioned raw JSON batch persistence."""

    def test_save_batch_creates_partitioned_file(self, tmp_path: Path):
        storage = RawStorageManager(base_data_dir=tmp_path)
        payload = {
            "metadata": {"batch_id": "batch-001"},
            "records": [{"id": 1}, {"id": 2}],
        }

        manifest = storage.save_batch(
            source_name="TRAFFIC",
            batch_id="batch-001",
            data=payload,
            partition_date="2026-11-24",
            subfolder="traffic",
        )

        target_file = Path(manifest["file_path"])
        assert target_file.exists()
        assert target_file.parent.name == "2026-11-24"
        assert target_file.name == "traffic_batch_batch-001.json"
        assert manifest["record_count"] == 2
        assert len(manifest["sha256_checksum"]) == 64

        # Read back saved file
        with open(target_file, "r", encoding="utf-8") as f:
            saved_json = json.load(f)
        assert saved_json == payload

    def test_save_batch_immutability_prevents_overwrite(self, tmp_path: Path):
        storage = RawStorageManager(base_data_dir=tmp_path)
        payload = {"records": [{"id": 1}]}

        # First save succeeds
        storage.save_batch(
            source_name="TRAFFIC",
            batch_id="batch-duplicate",
            data=payload,
            partition_date="2026-11-24",
            subfolder="traffic",
        )

        # Second save with identical batch_id and partition MUST raise BatchAlreadyExistsError
        with pytest.raises(BatchAlreadyExistsError) as exc_info:
            storage.save_batch(
                source_name="TRAFFIC",
                batch_id="batch-duplicate",
                data=payload,
                partition_date="2026-11-24",
                subfolder="traffic",
            )
        assert "already exists" in str(exc_info.value).lower()

    def test_manifest_file_appends_records(self, tmp_path: Path):
        storage = RawStorageManager(base_data_dir=tmp_path)
        storage.save_batch("SRC_A", "b1", {"records": [1]}, partition_date="2026-11-24", subfolder="test")
        storage.save_batch("SRC_A", "b2", {"records": [2]}, partition_date="2026-11-24", subfolder="test")

        manifest_file = tmp_path / "raw" / "ingestion_manifest.jsonl"
        assert manifest_file.exists()

        lines = manifest_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        record_1 = json.loads(lines[0])
        record_2 = json.loads(lines[1])
        assert record_1["batch_id"] == "b1"
        assert record_2["batch_id"] == "b2"

    def test_save_rejected_records_quarantine(self, tmp_path: Path):
        storage = RawStorageManager(base_data_dir=tmp_path)
        rejected = [
            {"sensor_id": "", "rejection_reasons": ["MISSING_OR_EMPTY_SENSOR_ID"]}
        ]

        manifest = storage.save_rejected_records(
            source_name="TRAFFIC",
            batch_id="batch-bad-001",
            rejected_records=rejected,
            partition_date="2026-11-24",
        )

        assert manifest is not None
        target_file = Path(manifest["file_path"])
        assert target_file.exists()
        assert "rejected" in str(target_file)
        assert manifest["record_count"] == 1
