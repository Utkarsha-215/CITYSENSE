"""
CITYSENSE Platform - Smart City Mobility Router
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.schemas import CorridorRanking, ZoneKPISchema, ZoneSummary
from src.api.services import DataService

router = APIRouter(prefix="/mobility", tags=["Urban Mobility"])


def get_data_service() -> DataService:
    return DataService()


@router.get("/zones", response_model=List[ZoneSummary])
def get_zones(
    date: Optional[str] = Query(None, description="Date partition YYYY-MM-DD (defaults to latest)"),
    service: DataService = Depends(get_data_service),
) -> List[ZoneSummary]:
    """Retrieve summarized mobility indicators across all monitored city zones."""
    summaries = service.get_zone_summaries(date=date)
    return [ZoneSummary(**s) for s in summaries]


@router.get("/zones/{zone_id}/kpis", response_model=List[ZoneKPISchema])
def get_zone_kpis(
    zone_id: str,
    date: Optional[str] = Query(None, description="Date partition YYYY-MM-DD (defaults to latest)"),
    service: DataService = Depends(get_data_service),
) -> List[ZoneKPISchema]:
    """Retrieve hourly mobility indicators for a specific zone."""
    kpis = service.get_zone_kpis(zone_id=zone_id, date=date)
    if not kpis:
        raise HTTPException(
            status_code=404,
            detail=f"Zone '{zone_id}' not found or no KPI data available for date '{date or 'latest'}'",
        )
    return [ZoneKPISchema(**k) for k in kpis]


@router.get("/corridors/congestion", response_model=List[CorridorRanking])
def get_corridors_congestion(
    date: Optional[str] = Query(None, description="Date partition YYYY-MM-DD (defaults to latest)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of corridors to return"),
    service: DataService = Depends(get_data_service),
) -> List[CorridorRanking]:
    """Rank smart city road corridors by congestion score and speed deficit."""
    rankings = service.get_corridor_rankings(date=date, limit=limit)
    return [CorridorRanking(**r) for r in rankings]
