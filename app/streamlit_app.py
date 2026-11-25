"""
CITYSENSE Platform - Interactive Smart City Mobility & Operations Dashboard
"""

import os
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.services import DataService

st.set_page_config(
    page_title="CITYSENSE - Smart City Mobility Intelligence",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .header-title {
        color: #0D47A1;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

service = DataService()

# Sidebar
st.sidebar.title("🏙️ CITYSENSE")
st.sidebar.caption("Smart City Mobility & Infrastructure Intelligence")
st.sidebar.markdown("---")

available_dates = service.discover_dates()
if not available_dates:
    st.sidebar.warning("No data partitions discovered. Run the ingestion and transformation pipeline first.")
    selected_date = None
else:
    selected_date = st.sidebar.selectbox("Select Date Partition", available_dates, index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("**Platform Status**: 🟢 Active")
st.sidebar.markdown("**City**: Pune, India")
st.sidebar.markdown("**Coordinates**: `18.5204° N, 73.8567° E`")
st.sidebar.markdown("**Attribution**: Open-Meteo (CC BY 4.0)")

# Main Header
st.title("🏙️ CITYSENSE: Urban Mobility Operations Cockpit")
st.caption(f"Real-time and analytical intelligence across smart city corridors | Partition: `{selected_date or 'N/A'}`")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Executive Mobility Overview",
    "🚦 Corridor Bottlenecks",
    "🌧️ Weather-Mobility Impact",
    "⚙️ Lakehouse Observability",
])

# ----------------- TAB 1: EXECUTIVE OVERVIEW -----------------
with tab1:
    st.subheader("Urban Mobility Health Summary")
    summaries = service.get_zone_summaries(date=selected_date)

    if summaries:
        df_summary = pd.DataFrame(summaries)
        col1, col2, col3, col4 = st.columns(4)

        total_volume = df_summary["total_volume"].sum()
        avg_speed = round(df_summary["avg_speed_kmh"].mean(), 1)
        avg_occ = round(df_summary["avg_occupancy_pct"].mean(), 1)
        peak_cong = round(df_summary["peak_congestion_score"].max(), 1)

        with col1:
            st.metric("Total Monitored Volume", f"{total_volume:,} vehicles")
        with col2:
            st.metric("Network Avg Speed", f"{avg_speed} km/h")
        with col3:
            st.metric("Avg Road Occupancy", f"{avg_occ}%")
        with col4:
            st.metric("Peak Congestion Score", f"{peak_cong} / 100")

        st.markdown("### Zone-Level Performance Metrics")
        st.dataframe(
            df_summary[[
                "zone_name", "total_volume", "avg_speed_kmh",
                "avg_occupancy_pct", "avg_congestion_score",
                "peak_congestion_score", "sensor_count"
            ]],
            use_container_width=True,
            column_config={
                "zone_name": "Urban Mobility Zone",
                "total_volume": "Volume",
                "avg_speed_kmh": "Avg Speed (km/h)",
                "avg_occupancy_pct": "Occupancy (%)",
                "avg_congestion_score": "Mean Congestion (0-100)",
                "peak_congestion_score": "Peak Congestion",
                "sensor_count": "Active Sensors",
            },
            hide_index=True,
        )

        st.markdown("### Congestion Index Across Zones")
        chart_data = df_summary.set_index("zone_name")[["avg_congestion_score", "peak_congestion_score"]]
        st.bar_chart(chart_data)
    else:
        st.info("No zone summary data available for this partition.")

# ----------------- TAB 2: CORRIDOR BOTTLENECKS -----------------
with tab2:
    st.subheader("Corridor Congestion Rankings & Bottleneck Detection")
    rankings = service.get_corridor_rankings(date=selected_date, limit=20)

    if rankings:
        df_rank = pd.DataFrame(rankings)
        st.dataframe(
            df_rank[[
                "road_name", "zone_id", "congestion_score",
                "congestion_level", "average_speed_kmh",
                "speed_limit_kmh", "road_occupancy_pct"
            ]],
            use_container_width=True,
            column_config={
                "road_name": "Corridor Name",
                "zone_id": "Zone Code",
                "congestion_score": "Congestion Score (0-100)",
                "congestion_level": "Severity Tier",
                "average_speed_kmh": "Speed (km/h)",
                "speed_limit_kmh": "Limit (km/h)",
                "road_occupancy_pct": "Occupancy (%)",
            },
            hide_index=True,
        )

        st.markdown("### Speed vs. Speed Limit by Corridor")
        chart_df = df_rank.set_index("road_name")[["average_speed_kmh", "speed_limit_kmh"]]
        st.bar_chart(chart_df)
    else:
        st.info("No corridor ranking data available for this partition.")

# ----------------- TAB 3: WEATHER-MOBILITY IMPACT -----------------
with tab3:
    st.subheader("Meteorological Impact on Traffic Velocity")
    impact = service.get_weather_impact_analysis(date=selected_date)

    col1, col2, col3 = st.columns(3)
    norm = impact.get("normal_conditions", {})
    disrupt = impact.get("disrupted_conditions", {})

    with col1:
        st.metric(
            "Normal Weather Speed",
            f"{norm.get('avg_speed_kmh', 0.0)} km/h",
            f"{norm.get('sample_count', 0)} readings"
        )
    with col2:
        st.metric(
            "Adverse Weather Speed",
            f"{disrupt.get('avg_speed_kmh', 0.0)} km/h",
            f"-{impact.get('speed_reduction_pct', 0.0)}% slowdown"
        )
    with col3:
        st.metric(
            "Congestion Surge",
            f"{disrupt.get('avg_congestion_score', 0.0)} / 100",
            f"+{impact.get('congestion_increase_pct', 0.0)}% increase"
        )

    st.markdown("---")
    st.markdown("""
    **Atmospheric Thresholds**:
    - **Rain Disruption**: Hourly precipitation $> 1.0\text{ mm}$
    - **Wind Hazard**: Sustained wind speed $> 30.0\text{ km/h}$
    """)

# ----------------- TAB 4: LAKEHOUSE OBSERVABILITY -----------------
with tab4:
    st.subheader("Data Lakehouse Audit Manifests & Quality Lineage")

    st.markdown("#### Bronze Raw Ingestion Audit Trail")
    raw_manifests = service.get_ingestion_manifest(limit=25)
    if raw_manifests:
        df_raw_m = pd.DataFrame(raw_manifests)
        cols_to_show = [c for c in ["batch_id", "source_name", "record_count", "ingestion_status", "sha256_checksum"] if c in df_raw_m.columns]
        st.dataframe(df_raw_m[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("No raw ingestion manifest records found.")

    st.markdown("#### Medallion Processing Transformation Manifest")
    proc_manifests = service.get_processing_manifest(limit=25)
    if proc_manifests:
        df_proc_m = pd.DataFrame(proc_manifests)
        st.dataframe(df_proc_m, use_container_width=True, hide_index=True)
    else:
        st.info("No processing manifest records found.")
