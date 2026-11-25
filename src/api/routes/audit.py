"""
CITYSENSE Platform - Data Lakehouse Audit Router
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from src.api.schemas import AuditRecord
from src.api.services import DataService

router = APIRouter(prefix="/audit", tags=["Lakehouse Audit & Lineage"])


def get_data_service() -> DataService:
    return DataService()


@router.get("/ingestion", response_model=List[AuditRecord])
def get_ingestion_manifest(
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to retrieve"),
    service: DataService = Depends(get_data_service),
) -> List[AuditRecord]:
    """Return raw ingestion batch lineage audit records with SHA-256 checksums."""
    records = service.get_ingestion_manifest(limit=limit)
    return [AuditRecord(**r) for r in records]


@router.get("/processing", response_model=List[Dict[str, Any]])
def get_processing_manifest(
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to retrieve"),
    service: DataService = Depends(get_data_service),
) -> List[Dict[str, Any]]:
    """Return Medallion transformation processing logs."""
    return service.get_processing_manifest(limit=limit)
