"""
CITYSENSE Platform - Weather Data Quality Validator
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.quality.base import BaseValidator, ValidationResult
from src.utils.logger import StructuredEventLogger, setup_logger


class WeatherDataValidator(BaseValidator):
    """
    Enforces meteorological and structural validation rules on weather observations.

    Rules:
    - Missing weather timestamp -> REJECT
    - Invalid temperature (< -50.0°C or > 65.0°C) -> REJECT
    - Invalid relative humidity (< 0.0% or > 100.0%) -> REJECT
    - Invalid rainfall (< 0.0 mm) -> REJECT
    - Invalid wind speed (< 0.0 km/h) -> REJECT
    """

    def __init__(self, event_logger: Optional[StructuredEventLogger] = None):
        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.quality.weather")
            self.logger = StructuredEventLogger(std_logger)

    def validate_record(self, record: Dict[str, Any]) -> List[str]:
        """
        Validate a single hourly weather record against physical atmospheric constraints.
        """
        reasons: List[str] = []

        # 1. Missing weather timestamp
        timestamp = record.get("timestamp")
        if not timestamp or not str(timestamp).strip():
            reasons.append("MISSING_WEATHER_TIMESTAMP: Weather record timestamp is required.")
        else:
            try:
                # Open-Meteo returns timestamps like '2026-11-24T00:00'
                datetime.fromisoformat(str(timestamp))
            except ValueError:
                reasons.append(f"INVALID_WEATHER_TIMESTAMP_FORMAT: Timestamp '{timestamp}' is not valid ISO format.")

        # 2. Temperature validation (-50°C to 65°C)
        temp = record.get("temperature_2m")
        if temp is None:
            reasons.append("MISSING_TEMPERATURE: 'temperature_2m' is required.")
        elif not isinstance(temp, (int, float)) or temp < -50.0 or temp > 65.0:
            reasons.append(f"INVALID_TEMPERATURE_VALUE: 'temperature_2m' must be between -50°C and 65°C, got {temp}.")

        # 3. Relative humidity validation (0% to 100%)
        humidity = record.get("relative_humidity_2m")
        if humidity is None:
            reasons.append("MISSING_HUMIDITY: 'relative_humidity_2m' is required.")
        elif not isinstance(humidity, (int, float)) or humidity < 0.0 or humidity > 100.0:
            reasons.append(f"INVALID_HUMIDITY_VALUE: 'relative_humidity_2m' must be between 0.0% and 100.0%, got {humidity}.")

        # 4. Rainfall validation (>= 0.0 mm)
        rain = record.get("rain")
        if rain is not None:
            if not isinstance(rain, (int, float)) or rain < 0.0:
                reasons.append(f"INVALID_RAINFALL_VALUE: 'rain' must be non-negative (>= 0.0 mm), got {rain}.")

        # 5. Wind speed validation (>= 0.0 km/h)
        wind_speed = record.get("wind_speed_10m")
        if wind_speed is not None:
            if not isinstance(wind_speed, (int, float)) or wind_speed < 0.0:
                reasons.append(f"INVALID_WIND_SPEED_VALUE: 'wind_speed_10m' must be non-negative, got {wind_speed}.")

        return reasons

    def validate_records(self, records: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate all unrolled hourly weather records and separate valid from rejected.
        """
        valid_records: List[Dict[str, Any]] = []
        rejected_records: List[Dict[str, Any]] = []

        for record in records:
            reasons = self.validate_record(record)
            if not reasons:
                valid_records.append(record)
            else:
                rejected_item = dict(record)
                rejected_item["rejection_reasons"] = reasons
                rejected_records.append(rejected_item)
                for reason in reasons:
                    self.logger.validation_error(
                        source_name="OPEN_METEO_WEATHER_API",
                        reason=reason,
                        timestamp=record.get("timestamp"),
                    )

        result = ValidationResult(
            source_name="OPEN_METEO_WEATHER_API",
            valid_records=valid_records,
            rejected_records=rejected_records,
        )

        self.logger.validation_evaluated(
            source_name="OPEN_METEO_WEATHER_API",
            valid_count=result.valid_count,
            rejected_count=result.rejected_count,
        )

        return result
