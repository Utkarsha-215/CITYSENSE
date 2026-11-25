"""
CITYSENSE Platform - Central Configuration Module
"""

import os
from pathlib import Path
from typing import Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings with environment variable overrides and sensible defaults.
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Runtime Environment
    CITYSENSE_ENV: str = Field(default="development", description="Runtime environment (development, staging, production)")
    LOG_LEVEL: str = Field(default="INFO", description="Standard logging level")

    # Project Paths
    PROJECT_ROOT: Path = Field(default=BASE_DIR)
    DATA_DIR: Path = Field(default=BASE_DIR / "data")
    LOGS_DIR: Path = Field(default=BASE_DIR / "logs")
    CONFIG_DIR: Path = Field(default=BASE_DIR / "config")

    # Open-Meteo Weather Ingestion API
    WEATHER_API_BASE_URL: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        description="Open-Meteo forecast endpoint"
    )
    WEATHER_CITY_NAME: str = Field(default="Pune", description="Target city for weather observation")
    WEATHER_LATITUDE: float = Field(default=18.5204, description="City latitude (Pune)")
    WEATHER_LONGITUDE: float = Field(default=73.8567, description="City longitude (Pune)")
    WEATHER_TIMEOUT_CONNECT: float = Field(default=5.0, description="HTTP connection timeout in seconds")
    WEATHER_TIMEOUT_READ: float = Field(default=15.0, description="HTTP read timeout in seconds")
    WEATHER_MAX_RETRIES: int = Field(default=3, description="Maximum HTTP retries on transient errors")
    WEATHER_BACKOFF_FACTOR: float = Field(default=0.5, description="Exponential backoff factor for retries")

    # Traffic Sensor Simulator
    TRAFFIC_NUM_SENSORS: int = Field(default=25, description="Number of active virtual sensors")
    TRAFFIC_DEFAULT_SEED: int = Field(default=42, description="Default seed for reproducibility")
    TRAFFIC_ZONES_CONFIG: Path = Field(default=BASE_DIR / "config" / "zones.json")

    @property
    def http_timeouts(self) -> Tuple[float, float]:
        """Return (connect_timeout, read_timeout) tuple."""
        return (self.WEATHER_TIMEOUT_CONNECT, self.WEATHER_TIMEOUT_READ)


# Global singleton instance
settings = Settings()
