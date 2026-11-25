"""
CITYSENSE Platform - Pytest Configuration & Test Fixtures
"""

import json
from pathlib import Path
from typing import Any, Dict
import pytest


@pytest.fixture
def sample_weather_api_response() -> Dict[str, Any]:
    """Provides a realistic mocked Open-Meteo API response for Pune, India."""
    return {
        "latitude": 18.52,
        "longitude": 73.86,
        "generationtime_ms": 0.123,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 560.0,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "rain": "mm",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": [
                "2026-11-24T00:00",
                "2026-11-24T01:00",
                "2026-11-24T02:00",
                "2026-11-24T03:00",
            ],
            "temperature_2m": [22.4, 21.8, 20.9, 20.3],
            "relative_humidity_2m": [65.0, 68.0, 72.0, 75.0],
            "rain": [0.0, 0.0, 0.2, 0.0],
            "wind_speed_10m": [8.5, 7.2, 6.8, 5.5],
        },
    }


@pytest.fixture
def sample_valid_traffic_record() -> Dict[str, Any]:
    """Provides a compliant traffic sensor record."""
    return {
        "sensor_id": "PUN_SNS_001",
        "zone_id": "ZONE_CBD_SHIVAJI_NAGAR",
        "road_name": "FC Road",
        "timestamp": "2026-11-24T16:00:00+00:00",
        "vehicle_count": 85,
        "average_speed": 42.5,
        "road_occupancy": 56.6,
        "congestion_level": "MODERATE",
        "data_source_mode": "SIMULATED",
        "simulation_seed": 42,
    }


@pytest.fixture
def sample_zones_config(tmp_path: Path) -> Path:
    """Creates a temporary zones configuration file for isolated simulator testing."""
    config_file = tmp_path / "test_zones.json"
    zones = [
        {
            "zone_id": "ZONE_TEST_A",
            "zone_name": "Test Zone Alpha",
            "roads": ["Alpha Expressway", "Beta Boulevard"],
            "base_capacity": 100,
            "speed_limit_kmh": 60.0,
        },
        {
            "zone_id": "ZONE_TEST_B",
            "zone_name": "Test Zone Beta",
            "roads": ["Gamma Arterial", "Delta Lane"],
            "base_capacity": 150,
            "speed_limit_kmh": 40.0,
        },
    ]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(zones, f)
    return config_file
