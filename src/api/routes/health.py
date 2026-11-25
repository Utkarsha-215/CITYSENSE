"""
CITYSENSE Platform - Health and Diagnostics Router
"""

from fastapi import APIRouter, Depends
from src.api.schemas import HealthResponse
from src.api.services import DataService

router = APIRouter(prefix="/health", tags=["Health & Diagnostics"])


def get_data_service() -> DataService:
    return DataService()


@router.get("", response_model=HealthResponse)
def get_health(service: DataService = Depends(get_data_service)) -> HealthResponse:
    """Return platform status, environment, and discovered date partitions."""
    status_data = service.get_health_status()
    return HealthResponse(**status_data)
