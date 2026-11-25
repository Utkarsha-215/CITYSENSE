"""
CITYSENSE Platform - Traffic Data Quality Validator
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.quality.base import BaseValidator, ValidationResult
from src.utils.logger import StructuredEventLogger, setup_logger


class TrafficDataValidator(BaseValidator):
    """
    Enforces schema and physical boundary constraints on traffic sensor records.

    Rules:
    - Missing sensor_id -> REJECT
    - Missing or unparseable timestamp -> REJECT
    - Negative vehicle_count (< 0) -> REJECT
    - Invalid average_speed (< 0.0 or > 200.0 km/h) -> REJECT
    - Invalid road_occupancy (< 0.0% or > 100.0%) -> REJECT
    """

    def __init__(self, event_logger: Optional[StructuredEventLogger] = None):
        if event_logger:
            self.logger = event_logger
        else:
            std_logger = setup_logger("citysense.quality.traffic")
            self.logger = StructuredEventLogger(std_logger)

    def validate_record(self, record: Dict[str, Any]) -> List[str]:
        """
        Evaluate a single traffic record and return a list of failure reasons.
        Returns an empty list if the record is fully compliant.
        """
        reasons: List[str] = []

        # 1. Check sensor_id presence
        sensor_id = record.get("sensor_id")
        if not sensor_id or not str(sensor_id).strip():
            reasons.append("MISSING_OR_EMPTY_SENSOR_ID: 'sensor_id' is required and must not be empty.")

        # 2. Check timestamp presence and format
        timestamp = record.get("timestamp")
        if not timestamp or not str(timestamp).strip():
            reasons.append("MISSING_TIMESTAMP: 'timestamp' is required.")
        else:
            try:
                # Support ISO format
                datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                reasons.append(f"INVALID_TIMESTAMP_FORMAT: Unable to parse timestamp '{timestamp}' as ISO-8601.")

        # 3. Check vehicle_count non-negative integer
        vehicle_count = record.get("vehicle_count")
        if vehicle_count is None:
            reasons.append("MISSING_VEHICLE_COUNT: 'vehicle_count' must be present.")
        elif not isinstance(vehicle_count, (int, float)) or vehicle_count < 0:
            reasons.append(f"NEGATIVE_OR_INVALID_VEHICLE_COUNT: 'vehicle_count' must be >= 0, got {vehicle_count}.")

        # 4. Check average_speed bounds (0.0 to 200.0 km/h)
        speed = record.get("average_speed")
        if speed is None:
            reasons.append("MISSING_AVERAGE_SPEED: 'average_speed' is required.")
        elif not isinstance(speed, (int, float)) or speed < 0.0 or speed > 200.0:
            reasons.append(f"INVALID_SPEED_VALUE: 'average_speed' must be between 0.0 and 200.0 km/h, got {speed}.")

        # 5. Check road_occupancy bounds (0.0 to 100.0%)
        occupancy = record.get("road_occupancy")
        if occupancy is not None:
            if not isinstance(occupancy, (int, float)) or occupancy < 0.0 or occupancy > 100.0:
                reasons.append(f"INVALID_ROAD_OCCUPANCY: 'road_occupancy' must be between 0.0 and 100.0%, got {occupancy}.")

        return reasons

    def validate_records(self, records: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate all records in the batch, separating valid and rejected records.
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
                        source_name="TRAFFIC_SENSOR_SIMULATOR",
                        reason=reason,
                        sensor_id=record.get("sensor_id"),
                    )

        result = ValidationResult(
            source_name="TRAFFIC_SENSOR_SIMULATOR",
            valid_records=valid_records,
            rejected_records=rejected_records,
        )

        self.logger.validation_evaluated(
            source_name="TRAFFIC_SENSOR_SIMULATOR",
            valid_count=result.valid_count,
            rejected_count=result.rejected_count,
        )

        return result
