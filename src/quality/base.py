"""
CITYSENSE Platform - Data Quality Foundation & Base Validator
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ValidationResult:
    """
    Encapsulates the outcome of data quality validation for an ingestion batch.
    """
    source_name: str
    valid_records: List[Dict[str, Any]] = field(default_factory=list)
    rejected_records: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.valid_records) + len(self.rejected_records)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_records)

    @property
    def is_valid(self) -> bool:
        """True if all records passed validation without any rejections."""
        return self.rejected_count == 0

    def summary(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "total_count": self.total_count,
            "valid_count": self.valid_count,
            "rejected_count": self.rejected_count,
            "is_valid": self.is_valid,
        }


class BaseValidator(ABC):
    """
    Abstract base validator for all CITYSENSE data sources.
    """

    @abstractmethod
    def validate_records(self, records: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate a list of records and return separated valid and rejected collections.
        """
        pass
