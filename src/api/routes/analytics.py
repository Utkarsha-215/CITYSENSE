"""
CITYSENSE Platform - Analytics & Cross-Domain Intelligence Router
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from src.api.schemas import WeatherImpactResponse
from src.api.services import DataService

router = APIRouter(prefix="/analytics", tags=["Cross-Domain Analytics"])


def get_data_service() -> DataService:
    return DataService()


@router.get("/weather-impact", response_model=WeatherImpactResponse)
def get_weather_impact(
    date: Optional[str] = Query(None, description="Date partition YYYY-MM-DD (defaults to latest)"),
    service: DataService = Depends(get_data_service),
) -> WeatherImpactResponse:
    """Quantify mobility velocity degradation under adverse weather conditions (rain, high wind)."""
    impact_data = service.get_weather_impact_analysis(date=date)
    return WeatherImpactResponse(**impact_data)
