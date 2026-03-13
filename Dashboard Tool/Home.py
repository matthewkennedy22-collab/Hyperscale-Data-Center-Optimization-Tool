"""
Hyperscale Data Center Optimization Tool — Dashboard entry point.

Run from the parent project folder (Counties+Zones Database):
  streamlit run "Dashboard Tool/Home.py"
"""
import streamlit as st
import plotly.graph_objects as go

from _utils import render_sidebar, get_counties, get_county_centroids, get_county_color_map
from ui import apply_global_css, metric_row, back_to_top_button, page_top_anchor

st.set_page_config(
    page_title="Hyperscale Data Center Optimization",
    page_icon="•",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_global_css()
render_sidebar()
page_top_anchor()

# Hero
n_selected = len(st.session_state.get("selected_county_fips", []))
st.markdown("""
<div class="hero">
<h1>Hyperscale Data Center Optimization Tool</h1>
<p>PUE WUE cost, location/system comparison, weather comparison, and drought risk comparison. Select one or more counties in the sidebar, then explore Weather, System Comparison, and Drought pages.</p>
</div>
""", unsafe_allow_html=True)

# About this tool: scope, suggested use, constraints, data sources
with st.expander("About this tool — scope, use, constraints & data", expanded=False):
    st.markdown("""
    **Scope**  
    This dashboard supports **county-level comparison** of data-center cooling options: **Air Economizer (AE)** vs **Water Economizer (WEC)**. It shows PUE and WUE, effective electric and water costs (using state-level rates), weather patterns, drought risk, and weighted comparison with tailored insights. All underlying metrics are derived from hourly weather and simulation outputs rolled up by county and week (or month).

    **Suggested use**  
    - **Select one or more counties** in the sidebar.  
    - Use **Weather comparison** to see temperature, humidity, and pressure over time and how they relate to PUE/WUE.  
    - Use **System comparison** to compare AE vs WEC (PUE, WUE, effective cost in ¢/kWh IT and $/kWh IT, and cost over the year by week).  
    - Use **Drought risk comparison** to review drought index over 10 years and seasonal patterns.  
    - Use **Comparison insights** to set weights (electric cost, water cost, water scarcity) and see composite scores and text recommendations (e.g. best fit, high-drought areas, lowest cost).

    **Simulation tool (PUE & WUE)**  
    The PUE and WUE values come from a **thermodynamics-based simulation** by **Lei and Masanet** (Northwestern University / UC Santa Barbara). The model uses hourly climate and facility-system parameters to compute when economizers provide “free” cooling versus when mechanical chillers are needed, and derives **thermodynamically consistent** PUE and WUE for each hour.  
    - **AE (airside economizer + adiabatic cooling):** Uses outside air with pre-humidification; cooling tower and chiller back up when conditions are unfavorable.  
    - **WEC (waterside economizer):** Uses evaporative cooling towers; chiller supplements when wet-bulb temperature is too high.  
    The approach is validated against reported PUE (and, where available, WUE) from hyperscale data centers (e.g. Google, Facebook). Published work: *Energy* (2020) on location-specific PUE prediction, and *Resources, Conservation & Recycling* (2022) on climate- and technology-specific PUE and WUE for U.S. data centers. Simulation code is available from the authors (e.g. Data-center-PUE-prediction-tool and Data-Center-Water-footprint repositories).

    **Constraints**  
    - **Simulation parameters** (e.g. supply air setpoints, UPS efficiency, fan/pump pressures, chiller and cooling tower parameters) are held at **midpoints** (or a single representative set) in the runs that feed this dashboard; the published research uses parameter ranges for sensitivity and uncertainty.  
    - **IT load** is held **constant** (results are per unit IT power).  
    - Results are conditional on these assumptions and on the weather and pricing data used; they do not re-run the full uncertainty analysis.

    **Data sources**  
    - **Weather:** Hourly data from **Open-Meteo** (temperature, relative humidity, pressure). The rollup is built from the same hourly series used to drive the PUE/WUE simulation (e.g. 2024 or the years in the source CSV).  
    - **PUE / WUE:** From the **Lei & Masanet thermodynamics-based PUE/WUE simulation** (hourly by county), aggregated to county × week (or month) for this dashboard.  
    - **Pricing:** **State-level** electric (¢/kWh) and water ($/kgal) rates. Effective electric cost = PUE × electric rate (→ ¢/kWh IT). Effective water cost = WUE × water rate after converting WUE from L/kWh to kgal/kWh (→ $/kWh IT).  
    - **Drought:** Weekly county-level drought index (e.g. **2015–2024**) from the project’s drought data file; used for risk and water-scarcity weighting.  
    - **County list & map:** Counties from the simulation rollup; map locations from Census county population centers (or a local centroid file).
    """)

# Metrics row + data-setup callout
total_counties = 0
counties_df = get_counties()
if counties_df is not None and not counties_df.empty:
    total_counties = len(counties_df)

# First-time / data-setup callout
if total_counties == 0:
    st.error("**Data not ready.** Run the rollup script to build the county list and rollup. See README or sidebar.")
    st.code('python "Dashboard Tool/scripts/build_county_week_rollup.py"', language="bash")
elif total_counties < 100:
    st.warning("**Limited data.** You have only a few counties. To load all ~3,100 counties, run the week rollup on the full 4 GB CSV: `python \"Dashboard Tool/scripts/build_county_week_rollup.py\"` (uses FINAL_counties_with_pue_wue.csv in the AMPLYTICO folder).")

metrics = [
    (str(n_selected), "Counties selected"),
    (str(total_counties), "Counties in dataset"),
    ("AE vs WEC", "Cooling systems"),
]
st.markdown('<p class="section-header">At a glance</p>', unsafe_allow_html=True)
metric_row(metrics)

# Map + selected counties info (when counties are selected)
if n_selected > 0:
    st.markdown("")
    st.markdown("**Selected counties**")
    selected_fips = [str(f).zfill(5) for f in st.session_state.get("selected_county_fips", [])]
    if counties_df is not None and not counties_df.empty:
        selected_labels = counties_df[counties_df["county_fips"].astype(str).str.zfill(5).isin(selected_fips)]
        selected_labels = selected_labels.drop_duplicates("county_fips")
        names = (selected_labels["county_name"] + ", " + selected_labels["state_abbr"].astype(str)).tolist()
        st.caption(", ".join(names) if len(names) <= 10 else f"{len(names)} counties selected")
    centroids = get_county_centroids()
    if centroids is not None and not centroids.empty:
        map_df = centroids[centroids["county_fips"].isin(selected_fips)].copy()
        if not map_df.empty and counties_df is not None and not counties_df.empty:
            map_df = map_df.merge(
                counties_df[["county_fips", "county_name", "state_abbr"]].drop_duplicates("county_fips"),
                on="county_fips",
                how="left",
            )
            map_df["label"] = map_df["county_name"].fillna("") + ", " + map_df["state_abbr"].fillna("")
        else:
            map_df["label"] = map_df["county_fips"]
        if not map_df.empty:
            _, county_color_map = get_county_color_map()
            map_df = map_df.copy()
            map_df["color"] = map_df["label"].map(county_color_map).fillna("#0e7490")
            # Fixed US basemap (Carto light) with county points; each county uses its assigned color
            fig = go.Figure(
                go.Scattermapbox(
                    lat=map_df["latitude"],
                    lon=map_df["longitude"],
                    text=map_df["label"],
                    mode="markers+text",
                    textposition="top center",
                    marker=dict(
                        size=14,
                        color=map_df["color"].tolist(),
                        symbol="circle",
                        allowoverlap=True,
                    ),
                    textfont=dict(size=12, color="#0f172a"),
                    hoverinfo="text",
                    name="",
                )
            )
            fig.update_layout(
                title="Selected counties (approximate locations)",
                mapbox=dict(
                    style="carto-positron",
                    center=dict(lat=39.0, lon=-98.0),
                    zoom=3,
                ),
                margin=dict(l=0, r=0, t=40, b=0),
                height=420,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": False, "displayModeBar": True})
        else:
            st.caption("County locations could not be resolved for the selected FIPS.")
    else:
        st.caption("Map requires county centroids (downloaded automatically from Census on first use; check network or add *data/county_centroids.csv*).")

# Explore — clear button-style nav
st.markdown("")
st.markdown('<p class="section-header">Explore</p>', unsafe_allow_html=True)
st.markdown("""
<style>
/* Explore section: style the four nav buttons (columns with buttons on Home) */
.block-container [data-testid="column"] button {
    width: 100%;
    padding: 0.85rem 1rem !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border-radius: 10px !important;
    border: 1px solid #e2e8f0 !important;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
    color: #334155 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    transition: all 0.2s ease !important;
}
.block-container [data-testid="column"] button:hover {
    border-color: #0e7490 !important;
    background: linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 100%) !important;
    color: #0e7490 !important;
    box-shadow: 0 2px 8px rgba(14,116,144,0.2) !important;
}
</style>
""", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("Weather comparison", use_container_width=True, key="nav_weather"):
        st.switch_page("pages/1_Weather_Comparison.py")
with col2:
    if st.button("System comparison", use_container_width=True, key="nav_sys"):
        st.switch_page("pages/2_System_Comparison.py")
with col3:
    if st.button("Drought risk comparison", use_container_width=True, key="nav_drought"):
        st.switch_page("pages/2_Drought_Risk_Comparison.py")
with col4:
    if st.button("Comparison insights", use_container_width=True, key="nav_insights"):
        st.switch_page("pages/4_Comparison_Insights.py")

if n_selected == 0:
    st.caption("Select one or more counties in the sidebar to compare PUE, WUE, weather, and drought across locations.")
else:
    st.caption(f"{n_selected} count{'y' if n_selected == 1 else 'ies'} selected — open any page above to view analysis.")

back_to_top_button()
