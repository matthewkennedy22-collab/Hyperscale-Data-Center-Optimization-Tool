"""System comparison: AE vs WEC — PUE, WUE, and cost by county."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from _utils import render_sidebar, get_rollup, get_pricing, get_drought, get_drought_summary_by_county, selected_counties_df, ensure_data, get_county_color_map, lighten_hex, sort_df_by_county_order
from ui import apply_global_css, section_header, apply_chart_theme, metric_row, back_to_top_button, page_top_anchor

st.set_page_config(page_title="System comparison | County Dashboard", page_icon="•", layout="wide")
apply_global_css()
render_sidebar()
page_top_anchor()
ensure_data()

rollup = get_rollup()
pricing = get_pricing()
drought = get_drought()
drought_summary = get_drought_summary_by_county(drought) if drought is not None else None
df = selected_counties_df(rollup, pricing, drought_summary=drought_summary)
if df is None or df.empty:
    st.info("Select one or more counties in the sidebar to compare systems.")
    st.stop()

annual = (
    df.groupby(["county_fips", "county_name", "state_abbr"], as_index=False)
    .agg(
        AE_PUE=("AE_PUE", "mean"),
        AE_WUE=("AE_WUE", "mean"),
        WEC_PUE=("WEC_PUE", "mean"),
        WEC_WUE=("WEC_WUE", "mean"),
        effective_electric_AE=("effective_electric_AE", "mean"),
        effective_electric_WEC=("effective_electric_WEC", "mean"),
        effective_water_AE=("effective_water_AE", "mean"),
        effective_water_WEC=("effective_water_WEC", "mean"),
        electric_cents=("electric_cents_per_kwh", "first"),
        water_dollars=("water_dollars_per_kgal", "first"),
    )
)
# Order by sidebar selection so each county keeps the same color on every page
annual["County"] = annual["county_name"] + ", " + annual["state_abbr"]
annual = sort_df_by_county_order(annual, "County")
ordered_county_labels, county_color_map = get_county_color_map()

# Top-level title and metrics (insightful comparison, not averages)
st.markdown("### System comparison (AE vs WEC)")
st.caption("Annual average PUE, WUE, and effective cost by county. AE = Air Economizer, WEC = Water Economizer. Costs use state-level pricing; water cost may include a drought surge when surge and drought data are available.")

# Tabs: PUE | WUE | Cost
tab_pue, tab_wue, tab_cost = st.tabs(["PUE comparison", "WUE comparison", "Effective cost"])

with tab_pue:
    with st.expander("What is PUE, and when is the line flat?", expanded=True):
        st.markdown("""
**PUE (Power Usage Effectiveness)** is total facility power divided by IT power — how much extra energy (cooling, lighting, etc.) is needed per unit of IT load. Lower is better (1.0 = no overhead).

The underlying simulation uses a **fixed IT load** (constant per-kWh basis), so PUE = facility power ÷ IT load is always expressed per unit of IT power. That makes comparisons across counties and over time consistent.

- **PUE varies over the year** because cooling demand depends on weather: in hot or humid weeks more cooling is needed, so facility power rises and PUE goes up; in cool weeks economizers do more of the work and PUE drops. So we usually see **seasonal variation** — higher in summer, lower in winter for many climates.

- **When the PUE line is relatively flat**, it often means a **milder climate** or a location where ambient temperature and humidity don’t swing as much, so cooling load (and thus facility power) stays more stable week to week.
        """)
    section_header("PUE by county", "Power usage effectiveness — lower is better.")
    pue_cols = ["county_name", "state_abbr", "AE_PUE", "WEC_PUE"]
    pue_df = annual[pue_cols].round(4)
    pue_df = pue_df.rename(columns={"county_name": "County", "state_abbr": "State", "AE_PUE": "AE PUE", "WEC_PUE": "WEC PUE"})
    def _make_county_bg(color_map):
        def _apply(x):
            # Styler passes a Series when subset is one column, DataFrame when multiple
            if isinstance(x, pd.Series):
                return x.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}")
            return x.apply(lambda col: col.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}"))
        return _apply
    pue_styled = pue_df.style.apply(_make_county_bg(county_color_map), subset=["County"])
    try:
        st.dataframe(pue_styled, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(pue_df, use_container_width=True, hide_index=True)
    st.download_button("Download PUE (CSV)", pue_df.to_csv(index=False).encode("utf-8"), file_name="pue_by_county.csv", mime="text/csv", key="dl_pue")
    pue_long = annual.melt(id_vars=["county_fips", "county_name", "state_abbr"], value_vars=["AE_PUE", "WEC_PUE"], var_name="System", value_name="PUE")
    pue_long["System"] = pue_long["System"].map({"AE_PUE": "AE", "WEC_PUE": "WEC"})
    pue_long["County"] = pue_long["county_name"] + ", " + pue_long["state_abbr"]
    pue_long = pue_long.sort_values(["County", "System"]).reset_index(drop=True)
    # Color = county (same as everywhere); pattern = system (solid AE, striped WEC)
    fig_pue = px.bar(
        pue_long, x="County", y="PUE", color="County", pattern_shape="System",
        barmode="group", title="PUE by county",
        color_discrete_map=county_color_map,
        pattern_shape_sequence=["", "/"],
        pattern_shape_map={"AE": "", "WEC": "/"},
    )
    fig_pue = apply_chart_theme(fig_pue)
    fig_pue.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_pue, use_container_width=True)

    # PUE over time (line chart) — same format as Weather: x-axis by month
    period_col = "week" if "week" in df.columns else ("month" if "month" in df.columns else None)
    if period_col and all(c in df.columns for c in ["AE_PUE", "WEC_PUE"]):
        section_header("PUE over the year", "Data by week; axis labeled by month. Hover for exact values.")
        df_ts = df.copy()
        by_p = df_ts.groupby(["county_fips", "county_name", "state_abbr", period_col], as_index=False).agg(
            AE_PUE=("AE_PUE", "mean"), WEC_PUE=("WEC_PUE", "mean"),
        )
        by_p["County"] = by_p["county_name"] + ", " + by_p["state_abbr"]
        by_p = sort_df_by_county_order(by_p, "County")
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if period_col == "week":
            by_p["_x"] = by_p["week"]
            tickvals = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48]
            ticktext = month_names
        else:
            by_p["_x"] = by_p["month"]
            tickvals = list(range(1, 13))
            ticktext = month_names
        pue_ts = by_p.melt(
            id_vars=["County", period_col, "_x"],
            value_vars=["AE_PUE", "WEC_PUE"],
            var_name="System", value_name="PUE",
        )
        pue_ts["System"] = pue_ts["System"].map({"AE_PUE": "AE", "WEC_PUE": "WEC"})
        pue_ts = pue_ts.sort_values(["County", "_x", "System"]).reset_index(drop=True)
        fig_pue_line = px.line(
            pue_ts, x="_x", y="PUE", color="County", line_dash="System",
            title="PUE over the year",
            color_discrete_map=county_color_map,
        )
        fig_pue_line = apply_chart_theme(fig_pue_line, height=320)
        fig_pue_line.update_layout(
            xaxis_title="Month",
            xaxis=dict(
                tickvals=tickvals, ticktext=ticktext, tickangle=-45,
                tickfont=dict(size=14, color="#1f2937"),
                title_font=dict(size=14),
            ),
            margin=dict(b=100, r=180),
            legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", font=dict(size=11)),
        )
        st.plotly_chart(fig_pue_line, use_container_width=True)

with tab_wue:
    with st.expander("What is WUE, and why is the WEC line flat?", expanded=True):
        st.markdown("""
**WUE (Water Usage Effectiveness)** is water consumed per kWh of IT load (e.g. L/kWh IT). Lower is better.

The underlying PUE/WUE simulation uses a **fixed IT load** (constant per-kWh basis): all results are expressed per unit of IT power. That convention is what makes PUE and WUE comparable across sites and over time.

- **WEC (waterside economizer)** cooling is evaporative (cooling towers). Water use is tied directly to heat rejection, which scales with the fixed IT load. So water consumption tracks IT load in a consistent way, and **WUE = water ÷ IT load** stays relatively **flat** over the year—you see a nearly horizontal WEC line.

- **AE (air economizer)** uses water mainly for **adiabatic assist** when ambient conditions don’t allow full free cooling (e.g. hot or dry periods). Water use is highly weather-dependent, so WUE for AE **varies by season**—peaks in hot weeks, low when free cooling dominates.
        """)
    section_header("WUE by county", "Water usage effectiveness — lower is better.")
    wue_cols = ["county_name", "state_abbr", "AE_WUE", "WEC_WUE"]
    wue_df = annual[wue_cols].round(4)
    wue_df = wue_df.rename(columns={"county_name": "County", "state_abbr": "State", "AE_WUE": "AE WUE", "WEC_WUE": "WEC WUE"})
    wue_styled = wue_df.style.apply(_make_county_bg(county_color_map), subset=["County"])
    try:
        st.dataframe(wue_styled, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(wue_df, use_container_width=True, hide_index=True)
    st.download_button("Download WUE (CSV)", wue_df.to_csv(index=False).encode("utf-8"), file_name="wue_by_county.csv", mime="text/csv", key="dl_wue")
    wue_long = annual.melt(id_vars=["county_fips", "county_name", "state_abbr"], value_vars=["AE_WUE", "WEC_WUE"], var_name="System", value_name="WUE")
    wue_long["System"] = wue_long["System"].map({"AE_WUE": "AE", "WEC_WUE": "WEC"})
    wue_long["County"] = wue_long["county_name"] + ", " + wue_long["state_abbr"]
    wue_long = wue_long.sort_values(["County", "System"]).reset_index(drop=True)
    fig_wue = px.bar(
        wue_long, x="County", y="WUE", color="County", pattern_shape="System",
        barmode="group", title="WUE by county",
        color_discrete_map=county_color_map,
        pattern_shape_sequence=["", "/"],
        pattern_shape_map={"AE": "", "WEC": "/"},
    )
    fig_wue = apply_chart_theme(fig_wue)
    fig_wue.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_wue, use_container_width=True)

    # WUE over time (line chart) — same format as Weather: x-axis by month
    period_col_wue = "week" if "week" in df.columns else ("month" if "month" in df.columns else None)
    if period_col_wue and all(c in df.columns for c in ["AE_WUE", "WEC_WUE"]):
        section_header("WUE over the year", "Data by week; axis labeled by month. Hover for exact values.")
        df_ts_wue = df.copy()
        by_p_wue = df_ts_wue.groupby(["county_fips", "county_name", "state_abbr", period_col_wue], as_index=False).agg(
            AE_WUE=("AE_WUE", "mean"), WEC_WUE=("WEC_WUE", "mean"),
        )
        by_p_wue["County"] = by_p_wue["county_name"] + ", " + by_p_wue["state_abbr"]
        by_p_wue = sort_df_by_county_order(by_p_wue, "County")
        month_names_wue = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if period_col_wue == "week":
            by_p_wue["_x"] = by_p_wue["week"]
            tickvals_wue = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48]
            ticktext_wue = month_names_wue
        else:
            by_p_wue["_x"] = by_p_wue["month"]
            tickvals_wue = list(range(1, 13))
            ticktext_wue = month_names_wue
        wue_ts = by_p_wue.melt(
            id_vars=["County", period_col_wue, "_x"],
            value_vars=["AE_WUE", "WEC_WUE"],
            var_name="System", value_name="WUE",
        )
        wue_ts["System"] = wue_ts["System"].map({"AE_WUE": "AE", "WEC_WUE": "WEC"})
        wue_ts = wue_ts.sort_values(["County", "_x", "System"]).reset_index(drop=True)
        fig_wue_line = px.line(
            wue_ts, x="_x", y="WUE", color="County", line_dash="System",
            title="WUE over the year",
            color_discrete_map=county_color_map,
        )
        fig_wue_line = apply_chart_theme(fig_wue_line, height=320)
        fig_wue_line.update_layout(
            xaxis_title="Month",
            xaxis=dict(
                tickvals=tickvals_wue, ticktext=ticktext_wue, tickangle=-45,
                tickfont=dict(size=14, color="#1f2937"),
                title_font=dict(size=14),
            ),
            margin=dict(b=100, r=180),
            legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", font=dict(size=11)),
        )
        st.plotly_chart(fig_wue_line, use_container_width=True)

with tab_cost:
    section_header("Effective cost (PUE × electric, WUE × water)", "Electric and water both in ¢/kWh IT (water = WUE × state rate converted to cents).")
    # Water in cents for readability (store as $ in data, display as ¢)
    cost_df = annual[["county_name", "state_abbr", "effective_electric_AE", "effective_electric_WEC", "effective_water_AE", "effective_water_WEC"]].copy()
    cost_df["effective_water_AE"] = (cost_df["effective_water_AE"] * 100).round(3)
    cost_df["effective_water_WEC"] = (cost_df["effective_water_WEC"] * 100).round(3)
    cost_df = cost_df.rename(columns={
        "county_name": "County", "state_abbr": "State",
        "effective_electric_AE": "Electric (AE) ¢/kWh IT", "effective_electric_WEC": "Electric (WEC) ¢/kWh IT",
        "effective_water_AE": "Water (AE) ¢/kWh IT", "effective_water_WEC": "Water (WEC) ¢/kWh IT",
    })
    cost_df = cost_df.round(3)
    cost_styled = cost_df.style.apply(_make_county_bg(county_color_map), subset=["County"])
    try:
        st.dataframe(cost_styled, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(cost_df, use_container_width=True, hide_index=True)
    st.download_button("Download cost (CSV)", cost_df.to_csv(index=False).encode("utf-8"), file_name="effective_cost_by_county.csv", mime="text/csv", key="dl_cost")
    # Electric only (¢/kWh)
    elec_long = annual.melt(
        id_vars=["county_fips", "county_name", "state_abbr"],
        value_vars=["effective_electric_AE", "effective_electric_WEC"],
        var_name="System", value_name="Effective cost (¢/kWh IT)",
    )
    elec_long["System"] = elec_long["System"].map({"effective_electric_AE": "AE", "effective_electric_WEC": "WEC"})
    elec_long["County"] = elec_long["county_name"] + ", " + elec_long["state_abbr"]
    elec_long = elec_long.sort_values(["County", "System"]).reset_index(drop=True)
    fig_elec = px.bar(
        elec_long, x="County", y="Effective cost (¢/kWh IT)", color="County", pattern_shape="System",
        barmode="group", title="Effective electric cost (PUE × state rate) — ¢/kWh IT",
        color_discrete_map=county_color_map,
        pattern_shape_sequence=["", "/"],
        pattern_shape_map={"AE": "", "WEC": "/"},
    )
    fig_elec = apply_chart_theme(fig_elec)
    fig_elec.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_elec, use_container_width=True)
    # Water only (display in ¢/kWh IT)
    water_long = annual.copy()
    water_long["effective_water_AE"] = (water_long["effective_water_AE"] * 100).round(4)
    water_long["effective_water_WEC"] = (water_long["effective_water_WEC"] * 100).round(4)
    water_long = water_long.melt(
        id_vars=["county_fips", "county_name", "state_abbr"],
        value_vars=["effective_water_AE", "effective_water_WEC"],
        var_name="System", value_name="Effective cost (¢/kWh IT)",
    )
    water_long["System"] = water_long["System"].map({"effective_water_AE": "AE", "effective_water_WEC": "WEC"})
    water_long["County"] = water_long["county_name"] + ", " + water_long["state_abbr"]
    water_long = water_long.sort_values(["County", "System"]).reset_index(drop=True)
    fig_water = px.bar(
        water_long, x="County", y="Effective cost (¢/kWh IT)", color="County", pattern_shape="System",
        barmode="group", title="Effective water cost (WUE × state rate) — ¢/kWh IT",
        color_discrete_map=county_color_map,
        pattern_shape_sequence=["", "/"],
        pattern_shape_map={"AE": "", "WEC": "/"},
    )
    fig_water = apply_chart_theme(fig_water)
    fig_water.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_water, use_container_width=True)

    # Line charts: effective cost across weeks (or months) of the year — one line per location and system
    period_col = "week" if "week" in df.columns else ("month" if "month" in df.columns else None)
    if period_col and all(c in df.columns for c in ["effective_electric_AE", "effective_electric_WEC", "effective_water_AE", "effective_water_WEC"]):
        years = sorted([int(y) for y in df["year"].dropna().unique()]) if "year" in df.columns else []
        multi_year = len(years) > 1
        if multi_year:
            typical = st.checkbox("Typical year (average across years)", value=True, help="When on, averages each week/month across all available years.", key="typical_year_cost")
        else:
            typical = False

        section_header("Effective cost over the year", "Data by week; axis labeled by month. Hover for exact values.")

        # If multi-year and not typical, filter to a single year (latest) to keep lines interpretable
        df_line = df.copy()
        if multi_year and not typical:
            y = max(years)
            df_line = df_line[df_line["year"] == y].copy()

        # Aggregate by (county, period) so we get one value per week/month per county
        by_period = df_line.groupby(["county_fips", "county_name", "state_abbr", period_col], as_index=False).agg(
            effective_electric_AE=("effective_electric_AE", "mean"),
            effective_electric_WEC=("effective_electric_WEC", "mean"),
            effective_water_AE=("effective_water_AE", "mean"),
            effective_water_WEC=("effective_water_WEC", "mean"),
        )
        by_period["County"] = by_period["county_name"] + ", " + by_period["state_abbr"]
        by_period = sort_df_by_county_order(by_period, "County")
        month_names_cost = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if period_col == "week":
            by_period["_x"] = by_period["week"]
            tickvals_cost = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48]
            ticktext_cost = month_names_cost
        else:
            by_period["_x"] = by_period["month"]
            tickvals_cost = list(range(1, 13))
            ticktext_cost = month_names_cost

        # Electric: color = county, line_dash = system (solid AE, dashed WEC)
        elec_lines = by_period.melt(
            id_vars=["County", period_col, "_x"],
            value_vars=["effective_electric_AE", "effective_electric_WEC"],
            var_name="System", value_name="Effective cost (¢/kWh IT)",
        )
        elec_lines["System"] = elec_lines["System"].map({"effective_electric_AE": "AE", "effective_electric_WEC": "WEC"})
        elec_lines = elec_lines.sort_values(["County", "_x", "System"]).reset_index(drop=True)
        fig_elec_line = px.line(
            elec_lines, x="_x", y="Effective cost (¢/kWh IT)", color="County", line_dash="System",
            title="Effective electric cost (¢/kWh IT) over the year",
            color_discrete_map=county_color_map,
            line_dash_sequence=["solid", "dash"],
            line_dash_map={"AE": "solid", "WEC": "dash"},
        )
        fig_elec_line = apply_chart_theme(fig_elec_line, height=320)
        fig_elec_line.update_layout(
            xaxis_title="Month",
            xaxis=dict(
                tickvals=tickvals_cost, ticktext=ticktext_cost, tickangle=-45,
                tickfont=dict(size=14, color="#1f2937"),
                title_font=dict(size=14),
            ),
            margin=dict(b=100, r=180),
            legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", font=dict(size=11)),
        )
        st.plotly_chart(fig_elec_line, use_container_width=True)

        # Water: same format — color = county, line_dash = system (display in ¢/kWh IT)
        by_period_water = by_period.copy()
        by_period_water["effective_water_AE"] = (by_period_water["effective_water_AE"] * 100).round(4)
        by_period_water["effective_water_WEC"] = (by_period_water["effective_water_WEC"] * 100).round(4)
        water_lines = by_period_water.melt(
            id_vars=["County", period_col, "_x"],
            value_vars=["effective_water_AE", "effective_water_WEC"],
            var_name="System", value_name="Effective cost (¢/kWh IT)",
        )
        water_lines["System"] = water_lines["System"].map({"effective_water_AE": "AE", "effective_water_WEC": "WEC"})
        water_lines = water_lines.sort_values(["County", "_x", "System"]).reset_index(drop=True)
        fig_water_line = px.line(
            water_lines, x="_x", y="Effective cost (¢/kWh IT)", color="County", line_dash="System",
            title="Effective water cost (¢/kWh IT) over the year",
            color_discrete_map=county_color_map,
            line_dash_sequence=["solid", "dash"],
            line_dash_map={"AE": "solid", "WEC": "dash"},
        )
        fig_water_line = apply_chart_theme(fig_water_line, height=320)
        fig_water_line.update_layout(
            xaxis_title="Month",
            xaxis=dict(
                tickvals=tickvals_cost, ticktext=ticktext_cost, tickangle=-45,
                tickfont=dict(size=14, color="#1f2937"),
                title_font=dict(size=14),
            ),
            margin=dict(b=100, r=180),
            legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", font=dict(size=11)),
        )
        st.plotly_chart(fig_water_line, use_container_width=True)
    else:
        st.caption("Weekly (or monthly) rollup is required for the time-series cost comparison. Use the weekly rollup data to see effective cost by week of year.")

back_to_top_button()
