"""
CITYSENSE Platform - Custom Exception Hierarchy
"""


class CitySenseError(Exception):
    """Base exception for all CITYSENSE platform operations."""
    pass


class IngestionError(CitySenseError):
    """Raised when an error occurs during data ingestion from any source."""
    pass


class WeatherAPIError(IngestionError):
    """Base error for Open-Meteo Weather API ingestion."""
    pass


class WeatherAPIConnectionError(WeatherAPIError):
    """Raised when network connection fails or requests time out."""
    pass


class WeatherAPIHTTPError(WeatherAPIError):
    """Raised when the Open-Meteo API returns an HTTP error status (4xx, 5xx)."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class WeatherAPIDataError(WeatherAPIError):
    """Raised when the API returns an invalid or unexpected JSON payload."""
    pass


class TrafficSimulatorError(IngestionError):
    """Raised when synthetic traffic record generation fails."""
    pass


class ValidationError(CitySenseError):
    """Raised when data quality validation fails."""
    pass


class StorageError(CitySenseError):
    """Base error for data storage and persistence operations."""
    pass


class BatchAlreadyExistsError(StorageError):
    """Raised when an attempt is made to overwrite an existing immutable raw batch."""
    pass
