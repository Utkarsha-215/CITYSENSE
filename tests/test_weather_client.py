"""
CITYSENSE Platform - Weather Ingestion Client Unit Tests
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from src.ingestion.weather_client import WeatherIngestionClient
from src.utils.exceptions import (
    WeatherAPIConnectionError,
    WeatherAPIDataError,
    WeatherAPIHTTPError,
)


class TestWeatherIngestionClient:
    """Test suite for Open-Meteo weather ingestion client with full network isolation."""

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_success(self, mock_get, sample_weather_api_response):
        """Verify successful API retrieval wraps raw payload and produces valid metadata."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_weather_api_response
        mock_get.return_value = mock_response

        client = WeatherIngestionClient()
        envelope = client.fetch_weather_data(batch_id="test-batch-001")

        assert envelope["metadata"]["batch_id"] == "test-batch-001"
        assert envelope["metadata"]["source_name"] == "OPEN_METEO_WEATHER_API"
        assert envelope["metadata"]["city"] == "Pune"
        assert envelope["metadata"]["ingestion_status"] == "SUCCESS"
        assert "Open-Meteo" in envelope["metadata"]["attribution"]
        assert envelope["raw_payload"] == sample_weather_api_response

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_timeout_error(self, mock_get):
        """Verify request timeout raises WeatherAPIConnectionError."""
        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out after 5.0s")

        client = WeatherIngestionClient()
        with pytest.raises(WeatherAPIConnectionError) as exc_info:
            client.fetch_weather_data()

        assert "timed out" in str(exc_info.value).lower()

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_connection_error(self, mock_get):
        """Verify network connection failure raises WeatherAPIConnectionError."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed to establish new connection")

        client = WeatherIngestionClient()
        with pytest.raises(WeatherAPIConnectionError):
            client.fetch_weather_data()

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_http_error(self, mock_get):
        """Verify HTTP 429 / 500 status codes raise WeatherAPIHTTPError with details."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        client = WeatherIngestionClient()
        with pytest.raises(WeatherAPIHTTPError) as exc_info:
            client.fetch_weather_data()

        assert exc_info.value.status_code == 500
        assert "500" in str(exc_info.value)

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_invalid_json(self, mock_get):
        """Verify malformed JSON responses raise WeatherAPIDataError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON token")
        mock_response.text = "<html><body>502 Bad Gateway</body></html>"
        mock_get.return_value = mock_response

        client = WeatherIngestionClient()
        with pytest.raises(WeatherAPIDataError) as exc_info:
            client.fetch_weather_data()

        assert "parse" in str(exc_info.value).lower()

    @patch("src.ingestion.weather_client.requests.Session.get")
    def test_fetch_weather_missing_hourly_section(self, mock_get):
        """Verify response payload without 'hourly' section raises WeatherAPIDataError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "Invalid coordinates"}
        mock_get.return_value = mock_response

        client = WeatherIngestionClient()
        with pytest.raises(WeatherAPIDataError) as exc_info:
            client.fetch_weather_data()

        assert "'hourly' section missing" in str(exc_info.value)

    def test_unroll_hourly_records(self, sample_weather_api_response):
        """Verify columnar hourly arrays are properly mapped to individual observation rows."""
        envelope = {
            "metadata": {
                "batch_id": "batch-123",
                "city": "Pune",
                "latitude": 18.52,
                "longitude": 73.86,
            },
            "raw_payload": sample_weather_api_response,
        }

        records = WeatherIngestionClient.unroll_hourly_records(envelope)
        assert len(records) == 4

        first = records[0]
        assert first["batch_id"] == "batch-123"
        assert first["city"] == "Pune"
        assert first["timestamp"] == "2026-11-24T00:00"
        assert first["temperature_2m"] == 22.4
        assert first["relative_humidity_2m"] == 65.0
        assert first["rain"] == 0.0
        assert first["wind_speed_10m"] == 8.5
        assert first["source_name"] == "OPEN_METEO_WEATHER_API"
