"""
CITYSENSE Platform - Data Quality Validator Unit Tests
"""

import pytest
from src.quality.traffic_validator import TrafficDataValidator
from src.quality.weather_validator import WeatherDataValidator


class TestTrafficDataValidator:
    """Test suite for traffic record schema and boundary validation."""

    def test_valid_record_passes(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()
        result = validator.validate_records([sample_valid_traffic_record])

        assert result.is_valid is True
        assert result.valid_count == 1
        assert result.rejected_count == 0

    def test_missing_sensor_id_rejected(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()
        bad_record = dict(sample_valid_traffic_record)
        bad_record["sensor_id"] = ""

        result = validator.validate_records([bad_record])
        assert result.is_valid is False
        assert result.rejected_count == 1
        assert any("MISSING_OR_EMPTY_SENSOR_ID" in r for r in result.rejected_records[0]["rejection_reasons"])

    def test_missing_timestamp_rejected(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()
        bad_record = dict(sample_valid_traffic_record)
        bad_record["timestamp"] = None

        result = validator.validate_records([bad_record])
        assert result.is_valid is False
        assert result.rejected_count == 1
        assert any("MISSING_TIMESTAMP" in r for r in result.rejected_records[0]["rejection_reasons"])

    def test_negative_vehicle_count_rejected(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()
        bad_record = dict(sample_valid_traffic_record)
        bad_record["vehicle_count"] = -5

        result = validator.validate_records([bad_record])
        assert result.is_valid is False
        assert result.rejected_count == 1
        assert any("NEGATIVE_OR_INVALID_VEHICLE_COUNT" in r for r in result.rejected_records[0]["rejection_reasons"])

    def test_invalid_speed_values_rejected(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()

        # Negative speed
        bad_record_1 = dict(sample_valid_traffic_record, average_speed=-10.0)
        # Excessive speed > 200 km/h
        bad_record_2 = dict(sample_valid_traffic_record, average_speed=250.0)

        result = validator.validate_records([bad_record_1, bad_record_2])
        assert result.rejected_count == 2
        assert result.valid_count == 0

    def test_invalid_occupancy_rejected(self, sample_valid_traffic_record):
        validator = TrafficDataValidator()
        bad_record = dict(sample_valid_traffic_record, road_occupancy=120.0)

        result = validator.validate_records([bad_record])
        assert result.rejected_count == 1
        assert any("INVALID_ROAD_OCCUPANCY" in r for r in result.rejected_records[0]["rejection_reasons"])


class TestWeatherDataValidator:
    """Test suite for atmospheric meteorological constraints."""

    def test_valid_weather_record_passes(self):
        validator = WeatherDataValidator()
        record = {
            "timestamp": "2026-11-24T12:00",
            "temperature_2m": 25.5,
            "relative_humidity_2m": 55.0,
            "rain": 0.0,
            "wind_speed_10m": 12.0,
        }
        result = validator.validate_records([record])
        assert result.is_valid is True
        assert result.valid_count == 1

    def test_missing_weather_timestamp_rejected(self):
        validator = WeatherDataValidator()
        record = {
            "timestamp": None,
            "temperature_2m": 25.5,
            "relative_humidity_2m": 55.0,
        }
        result = validator.validate_records([record])
        assert result.rejected_count == 1
        assert any("MISSING_WEATHER_TIMESTAMP" in r for r in result.rejected_records[0]["rejection_reasons"])

    def test_extreme_temperature_rejected(self):
        validator = WeatherDataValidator()
        too_hot = {"timestamp": "2026-11-24T12:00", "temperature_2m": 75.0, "relative_humidity_2m": 40.0}
        too_cold = {"timestamp": "2026-11-24T12:00", "temperature_2m": -60.0, "relative_humidity_2m": 40.0}

        result = validator.validate_records([too_hot, too_cold])
        assert result.rejected_count == 2
        assert result.valid_count == 0

    def test_invalid_humidity_rejected(self):
        validator = WeatherDataValidator()
        high_humidity = {"timestamp": "2026-11-24T12:00", "temperature_2m": 22.0, "relative_humidity_2m": 105.0}
        neg_humidity = {"timestamp": "2026-11-24T12:00", "temperature_2m": 22.0, "relative_humidity_2m": -5.0}

        result = validator.validate_records([high_humidity, neg_humidity])
        assert result.rejected_count == 2

    def test_negative_rain_rejected(self):
        validator = WeatherDataValidator()
        neg_rain = {
            "timestamp": "2026-11-24T12:00",
            "temperature_2m": 22.0,
            "relative_humidity_2m": 60.0,
            "rain": -1.5,
        }
        result = validator.validate_records([neg_rain])
        assert result.rejected_count == 1
        assert any("INVALID_RAINFALL_VALUE" in r for r in result.rejected_records[0]["rejection_reasons"])
