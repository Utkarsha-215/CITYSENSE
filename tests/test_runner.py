"""
CITYSENSE Platform - Ingestion Pipeline Runner Integration Tests
"""

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from src.ingestion.runner import IngestionOrchestrator
from src.storage.raw_storage import RawStorageManager


class TestIngestionRunnerIntegration:
    """Integration test suite for the ingestion orchestrator."""

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_run_weather_ingestion_end_to_end(self, mock_get, sample_weather_api_response, tmp_path: Path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_weather_api_response
        mock_get.return_value = mock_response

        storage = RawStorageManager(base_data_dir=tmp_path)
        orchestrator = IngestionOrchestrator(storage_manager=storage)

        result = orchestrator.run_weather_ingestion(
            city_name="Pune",
            batch_id="weather-int-001",
        )

        assert result["status"] == "SUCCESS"
        assert result["batch_id"] == "weather-int-001"
        assert result["valid_records"] == 4
        assert result["rejected_records"] == 0

        # Check raw file written
        raw_file = Path(result["batch_manifest"]["file_path"])
        assert raw_file.exists()

    def test_run_traffic_ingestion_with_anomalies_quarantine(self, tmp_path: Path):
        storage = RawStorageManager(base_data_dir=tmp_path)
        orchestrator = IngestionOrchestrator(storage_manager=storage)

        result = orchestrator.run_traffic_ingestion(
            num_records=10,
            seed=42,
            batch_id="traffic-int-001",
            inject_anomalies=True,
        )

        assert result["status"] == "SUCCESS"
        assert result["valid_records"] == 10
        assert result["rejected_records"] == 2  # Two injected bad records
        assert result["rejected_manifest"] is not None

        # Verify valid batch file and quarantine file exist
        valid_file = Path(result["batch_manifest"]["file_path"])
        rejected_file = Path(result["rejected_manifest"]["file_path"])

        assert valid_file.exists()
        assert rejected_file.exists()
        assert "rejected" in str(rejected_file)
