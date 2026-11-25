"""
CITYSENSE Platform - Open-Meteo Weather Ingestion Client
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings
from src.utils.exceptions import (
    WeatherAPIConnectionError,
    WeatherAPIDataError,
    WeatherAPIHTTPError,
)
from src.utils.logger import StructuredEventLogger, setup_logger
from src.utils.time_utils import get_utc_iso_string


class WeatherIngestionClient:
    """
    Robust HTTP client for ingesting meteorological data from Open-Meteo API.
    Enforces timeout handling, retries with exponential backoff, and envelope packaging.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        city_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timeouts: Optional[Tuple[float, float]] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self.base_url = base_url or settings.WEATHER_API_BASE_URL
        self.city_name = city_name or settings.WEATHER_CITY_NAME
        self.latitude = latitude if latitude is not None else settings.WEATHER_LATITUDE
        self.longitude = longitude if longitude is not None else settings.WEATHER_LONGITUDE
        self.timeouts = timeouts or settings.http_timeouts
        self.max_retries = max_retries if max_retries is not None else settings.WEATHER_MAX_RETRIES
        self.backoff_factor = backoff_factor if backoff_factor is not None else settings.WEATHER_BACKOFF_FACTOR

        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.weather", settings.LOGS_DIR)
            self.logger = StructuredEventLogger(std_logger)

        self._session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        """Create a requests Session configured with urllib3 Retry for transient HTTP errors."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,  # We handle status codes explicitly for detailed diagnostics
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_weather_data(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch hourly weather forecast from Open-Meteo API and wrap it in an ingestion envelope.

        Returns:
            Dict containing metadata (batch_id, ingestion_timestamp, attribution) and raw_payload.
        """
        lat = latitude if latitude is not None else self.latitude
        lon = longitude if longitude is not None else self.longitude
        batch_id = batch_id or str(uuid.uuid4())

        self.logger.ingestion_started(
            source_name="OPEN_METEO_WEATHER_API",
            batch_id=batch_id,
            city=self.city_name,
            latitude=lat,
            longitude=lon,
        )

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,rain,wind_speed_10m",
            "timezone": "auto",
        }

        start_time = time.perf_counter()
        try:
            response = self._session.get(
                self.base_url,
                params=params,
                timeout=self.timeouts,
            )
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.Timeout) as e:
            err_msg = f"Request timed out while connecting to {self.base_url} with timeouts {self.timeouts}: {e}"
            self.logger.failed_request(source_name="OPEN_METEO_WEATHER_API", error=err_msg, batch_id=batch_id)
            raise WeatherAPIConnectionError(err_msg) from e
        except requests.exceptions.ConnectionError as e:
            err_msg = f"Network connection failed when reaching {self.base_url}: {e}"
            self.logger.failed_request(source_name="OPEN_METEO_WEATHER_API", error=err_msg, batch_id=batch_id)
            raise WeatherAPIConnectionError(err_msg) from e
        except requests.exceptions.RequestException as e:
            err_msg = f"Unexpected request error occurred: {e}"
            self.logger.failed_request(source_name="OPEN_METEO_WEATHER_API", error=err_msg, batch_id=batch_id)
            raise WeatherAPIError(err_msg) from e

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Check HTTP status code
        if response.status_code >= 400:
            err_msg = f"Open-Meteo API returned HTTP {response.status_code}: {response.text[:200]}"
            self.logger.failed_request(
                source_name="OPEN_METEO_WEATHER_API",
                error=err_msg,
                status_code=response.status_code,
                batch_id=batch_id,
            )
            raise WeatherAPIHTTPError(
                message=err_msg,
                status_code=response.status_code,
                response_body=response.text,
            )

        # Decode JSON response
        try:
            raw_json = response.json()
        except ValueError as e:
            err_msg = f"Failed to parse Open-Meteo response as JSON: {response.text[:200]}"
            self.logger.failed_request(source_name="OPEN_METEO_WEATHER_API", error=err_msg, batch_id=batch_id)
            raise WeatherAPIDataError(err_msg) from e

        if not isinstance(raw_json, dict) or "hourly" not in raw_json:
            err_msg = f"Invalid API payload structure: 'hourly' section missing from response"
            self.logger.failed_request(source_name="OPEN_METEO_WEATHER_API", error=err_msg, batch_id=batch_id)
            raise WeatherAPIDataError(err_msg)

        self.logger.api_response_received(
            source_name="OPEN_METEO_WEATHER_API",
            status_code=response.status_code,
            latency_ms=latency_ms,
            batch_id=batch_id,
        )

        envelope: Dict[str, Any] = {
            "metadata": {
                "batch_id": batch_id,
                "source_name": "OPEN_METEO_WEATHER_API",
                "ingestion_timestamp": get_utc_iso_string(),
                "city": self.city_name,
                "latitude": lat,
                "longitude": lon,
                "endpoint": self.base_url,
                "latency_ms": latency_ms,
                "attribution": "Weather data provided by Open-Meteo.com under CC BY 4.0",
                "ingestion_status": "SUCCESS",
            },
            "raw_payload": raw_json,
        }
        return envelope

    @staticmethod
    def unroll_hourly_records(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Unroll the columnar hourly arrays from the Open-Meteo raw payload into individual row records
        suitable for data quality validation and downstream analytical processing.
        """
        raw_payload = envelope.get("raw_payload", {})
        hourly = raw_payload.get("hourly", {})
        metadata = envelope.get("metadata", {})

        timestamps = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        rains = hourly.get("rain", [])
        wind_speeds = hourly.get("wind_speed_10m", [])

        num_records = len(timestamps)
        records: List[Dict[str, Any]] = []

        for i in range(num_records):
            record = {
                "batch_id": metadata.get("batch_id"),
                "city": metadata.get("city", "Pune"),
                "latitude": metadata.get("latitude"),
                "longitude": metadata.get("longitude"),
                "timestamp": timestamps[i] if i < len(timestamps) else None,
                "temperature_2m": temperatures[i] if i < len(temperatures) else None,
                "relative_humidity_2m": humidities[i] if i < len(humidities) else None,
                "rain": rains[i] if i < len(rains) else None,
                "wind_speed_10m": wind_speeds[i] if i < len(wind_speeds) else None,
                "source_name": "OPEN_METEO_WEATHER_API",
                "attribution": "Weather data provided by Open-Meteo.com under CC BY 4.0",
            }
            records.append(record)

        return records
