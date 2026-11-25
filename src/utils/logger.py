"""
CITYSENSE Platform - Structured JSON Logging Engine
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    Formats log records into machine-readable JSON strings for production observability.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Include structured event attributes if passed via extra
        if hasattr(record, "event_name"):
            log_payload["event_name"] = record.event_name

        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_payload.update(record.extra_fields)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logger(
    name: str = "citysense",
    log_dir: Optional[Path] = None,
    log_file: str = "citysense.log",
    log_level: str = "INFO"
) -> logging.Logger:
    """
    Configure and return a structured logger with both console and rotating/file handlers.
    """
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    formatter = JSONFormatter()

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / log_file
        file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


class StructuredEventLogger:
    """
    Convenience wrapper providing explicit structured logging methods for data engineering lifecycle events.
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def log_event(self, event_name: str, message: str, level: str = "INFO", **kwargs):
        """Log a structured domain event with custom keyword fields."""
        extra = {"event_name": event_name, "extra_fields": kwargs}
        log_func = getattr(self._logger, level.lower(), self._logger.info)
        log_func(message, extra=extra)

    def ingestion_started(self, source_name: str, batch_id: str, **kwargs):
        self.log_event(
            event_name="INGESTION_STARTED",
            message=f"Ingestion started for source: {source_name}",
            level="INFO",
            source_name=source_name,
            batch_id=batch_id,
            **kwargs
        )

    def api_response_received(self, source_name: str, status_code: int, latency_ms: float, **kwargs):
        self.log_event(
            event_name="API_RESPONSE_RECEIVED",
            message=f"API response received from {source_name} with status {status_code}",
            level="INFO",
            source_name=source_name,
            status_code=status_code,
            latency_ms=latency_ms,
            **kwargs
        )

    def records_extracted(self, source_name: str, record_count: int, **kwargs):
        self.log_event(
            event_name="RECORDS_EXTRACTED",
            message=f"Extracted {record_count} records from {source_name}",
            level="INFO",
            source_name=source_name,
            record_count=record_count,
            **kwargs
        )

    def validation_evaluated(self, source_name: str, valid_count: int, rejected_count: int, **kwargs):
        self.log_event(
            event_name="VALIDATION_EVALUATED",
            message=f"Validation completed for {source_name}: {valid_count} valid, {rejected_count} rejected",
            level="INFO" if rejected_count == 0 else "WARNING",
            source_name=source_name,
            valid_count=valid_count,
            rejected_count=rejected_count,
            **kwargs
        )

    def records_saved(self, source_name: str, file_path: str, record_count: int, **kwargs):
        self.log_event(
            event_name="RECORDS_SAVED",
            message=f"Saved {record_count} records for {source_name} to {file_path}",
            level="INFO",
            source_name=source_name,
            file_path=file_path,
            record_count=record_count,
            **kwargs
        )

    def failed_request(self, source_name: str, error: str, retry_count: int = 0, **kwargs):
        self.log_event(
            event_name="FAILED_REQUEST",
            message=f"Request to {source_name} failed: {error}",
            level="ERROR",
            source_name=source_name,
            error=error,
            retry_count=retry_count,
            **kwargs
        )

    def validation_error(self, source_name: str, reason: str, **kwargs):
        self.log_event(
            event_name="VALIDATION_ERROR",
            message=f"Validation error for {source_name}: {reason}",
            level="WARNING",
            source_name=source_name,
            reason=reason,
            **kwargs
        )
