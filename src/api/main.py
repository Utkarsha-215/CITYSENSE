"""
CITYSENSE Platform - FastAPI Application Factory
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.analytics import router as analytics_router
from src.api.routes.audit import router as audit_router
from src.api.routes.health import router as health_router
from src.api.routes.mobility import router as mobility_router

app = FastAPI(
    title="CITYSENSE: Smart City Intelligence API",
    description=(
        "Enterprise Data Serving Layer for CITYSENSE – Smart City Mobility & Infrastructure Intelligence Platform.\n\n"
        "Serves Silver cleansed and Gold curated analytical Parquet datasets with sub-millisecond columnar querying."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for dashboards and frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register v1 API Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(mobility_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
def root():
    return {
        "platform": "CITYSENSE",
        "service": "Smart City Mobility & Infrastructure Intelligence Serving Layer",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
