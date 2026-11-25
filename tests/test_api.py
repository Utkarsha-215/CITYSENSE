"""
CITYSENSE Platform - FastAPI Serving Layer Pytest Test Suite
"""

import pytest
from fastapi import HTTPException

from src.api.main import root
from src.api.routes.analytics import get_weather_impact
from src.api.routes.audit import get_ingestion_manifest, get_processing_manifest
from src.api.routes.health import get_health
from src.api.routes.mobility import get_corridors_congestion, get_zone_kpis, get_zones
from src.api.schemas import (
    AuditRecord,
    CorridorRanking,
    HealthResponse,
    WeatherImpactResponse,
    ZoneKPISchema,
    ZoneSummary,
)
from src.api.services import DataService


@pytest.fixture
def service():
    """Provides DataService instance for testing."""
    return DataService()


class TestCitySenseAPI:
    """Integration test suite for CITYSENSE REST API endpoints and data access layer."""

    def test_root_endpoint(self):
        """Verify root discovery endpoint returns metadata and documentation paths."""
        data = root()
        assert data["platform"] == "CITYSENSE"
        assert data["version"] == "1.0.0"
        assert "/docs" in data["docs"]
        assert "/health" in data["health"]

    def test_health_endpoint(self, service):
        """Verify health check endpoint returns status and discovered partitions."""
        health = get_health(service=service)
        assert isinstance(health, HealthResponse)
        assert health.status == "HEALTHY"
        assert health.environment in ("development", "production", "test")
        assert isinstance(health.available_dates, list)
        assert health.total_raw_manifest_batches >= 0

    def test_get_zones_summary(self, service):
        """Verify zones summary returns compliant list of ZoneSummary schemas."""
        summaries = get_zones(date=None, service=service)
        assert isinstance(summaries, list)
        if summaries:
            first_zone = summaries[0]
            assert isinstance(first_zone, ZoneSummary)
            assert first_zone.zone_id.startswith("ZONE_")
            assert first_zone.total_volume >= 0
            assert 0.0 <= first_zone.avg_congestion_score <= 100.0

    def test_get_zone_kpis_valid_zone(self, service):
        """Verify zone hourly KPIs return timeseries data for valid zone."""
        summaries = get_zones(date=None, service=service)
        if summaries:
            target_zone_id = summaries[0].zone_id
            kpis = get_zone_kpis(zone_id=target_zone_id, date=None, service=service)
            assert isinstance(kpis, list)
            if kpis:
                first_kpi = kpis[0]
                assert isinstance(first_kpi, ZoneKPISchema)
                assert first_kpi.zone_id == target_zone_id
                assert first_kpi.total_vehicle_volume >= 0
                assert 0.0 <= first_kpi.avg_congestion_score <= 100.0

    def test_get_zone_kpis_invalid_zone_raises_404(self, service):
        """Verify query for non-existent zone raises 404 HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            get_zone_kpis(zone_id="NON_EXISTENT_ZONE_XYZ_999", date=None, service=service)
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_get_corridors_congestion_ranking(self, service):
        """Verify corridor congestion rankings respect limit and sorting order."""
        rankings = get_corridors_congestion(date=None, limit=5, service=service)
        assert isinstance(rankings, list)
        assert len(rankings) <= 5
        if rankings:
            assert isinstance(rankings[0], CorridorRanking)
            assert rankings[0].speed_limit_kmh > 0
            assert 0.0 <= rankings[0].congestion_score <= 100.0
            # Verify sorted descending by congestion score
            scores = [r.congestion_score for r in rankings]
            assert scores == sorted(scores, reverse=True)

    def test_weather_impact_analytics(self, service):
        """Verify weather-mobility impact analysis produces valid comparative metrics."""
        impact = get_weather_impact(date=None, service=service)
        assert isinstance(impact, WeatherImpactResponse)
        assert hasattr(impact, "normal_conditions")
        assert hasattr(impact, "disrupted_conditions")
        assert impact.normal_conditions.sample_count >= 0
        assert impact.disrupted_conditions.sample_count >= 0

    def test_audit_ingestion_manifest(self, service):
        """Verify raw ingestion manifest returns list of AuditRecord models."""
        audit_records = get_ingestion_manifest(limit=10, service=service)
        assert isinstance(audit_records, list)
        if audit_records:
            first_record = audit_records[0]
            assert isinstance(first_record, AuditRecord)
            assert first_record.batch_id is not None
            assert first_record.source_name is not None

    def test_audit_processing_manifest(self, service):
        """Verify transformation processing manifest returns stage audit rows."""
        proc_records = get_processing_manifest(limit=10, service=service)
        assert isinstance(proc_records, list)
        if proc_records:
            first_proc = proc_records[0]
            assert isinstance(first_proc, dict)
            assert "status" in first_proc
