"""Weather comparison: time series, distributions, and PUE/WUE vs weather."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from _utils import render_sidebar, get_rollup, get_pricing, selected_counties_df, ensure_data, get_county_color_map, sort_df_by_county_order
from ui import apply_global_css, section_header, apply_chart_theme, metric_row, back_to_top_button, page_top_anchor

st.set_page_config(page_title="Weather comparison | County Dashboard", page_icon="•", layout="wide")
apply_global_css()
render_sidebar()
page_top_anchor()
ensure_data()

rollup = get_rollup()
pricing = get_pricing()
df = selected_counties_df(rollup, pricing)
if df is None or df.empty:
    st.info("Select one or more counties in the sidebar to view weather comparison.")
    st.stop()

df = df.copy()
df["County"] = df["county_name"] + ", " + df["state_abbr"]
df = sort_df_by_county_order(df, "County")
_, county_color_map = get_county_color_map()
# Support both weekly and monthly rollups
if "week" in df.columns:
    df["period_label"] = df["year"].astype(str) + "-W" + df["week"].astype(int).astype(str).str.zfill(2)
    df["period_sort"] = df["year"] * 100 + df["week"]
    period_col = "week"
else:
    df["period_label"] = pd.to_datetime(df["month"].astype(str) + "-01", format="%m-%d").dt.strftime("%b %Y")
    df["period_sort"] = df["year"] * 100 + df["month"]
    period_col = "month"

st.markdown("### Weather comparison")
year_min = int(df["year"].min()) if "year" in df.columns and pd.notna(df["year"].min()) else None
year_max = int(df["year"].max()) if "year" in df.columns and pd.notna(df["year"].max()) else None
if year_min is not None and year_max is not None:
    year_label = f"{year_min}" if year_min == year_max else f"{year_min}–{year_max}"
else:
    year_label = "unknown years"
period_label = "week" if period_col == "week" else "month"
st.caption(f"{'Weekly' if period_col == 'week' else 'Monthly'} averages from county × {period_label} rollup ({year_label}).")

# Temperature unit: °C or °F (data is stored in °C)
temp_unit = st.radio("Temperature unit", ["°C", "°F"], horizontal=True, key="weather_temp_unit")
use_fahrenheit = temp_unit == "°F"
if "temp_c" in df.columns:
    df["temp_display"] = (df["temp_c"] * 9/5 + 32) if use_fahrenheit else df["temp_c"]
temp_label = "Temperature (°F)" if use_fahrenheit else "Temperature (°C)"

# Per-county means for insight
county_weather = df.groupby("County", as_index=False).agg(temp_c=("temp_c", "mean"), rh_pct=("rh_pct", "mean"))
n_c = len(county_weather)
warmest = county_weather.loc[county_weather["temp_c"].idxmax()]
coolest = county_weather.loc[county_weather["temp_c"].idxmin()]
def _temp_str(t_c, fahrenheit):
    return f"{(t_c * 9/5 + 32):.1f}°F" if fahrenheit else f"{t_c:.1f}°C"
warm_label = f"{warmest['County']} ({_temp_str(warmest['temp_c'], use_fahrenheit)})"
cool_label = f"{coolest['County']} ({_temp_str(coolest['temp_c'], use_fahrenheit)})"
metric_row([
    (str(n_c), "Counties"),
    (warm_label[:28] + "…" if len(warm_label) > 28 else warm_label, "Warmest (avg temp)"),
    (cool_label[:28] + "…" if len(cool_label) > 28 else cool_label, "Coolest (avg temp)"),
])

# Tabs: Time series | Distributions | PUE/WUE vs weather
tab_ts, tab_dist, tab_pue_weather = st.tabs(["Time series", "Distributions", "PUE/WUE vs weather"])

with tab_ts:
    section_header("Temperature, humidity & pressure over time", "One chart per variable. Data is weekly; axis labeled by month.")
    ts_cols = ["temp_c", "rh_pct", "pressure_hpa"]
    if all(c in df.columns for c in ts_cols):
        # Weekly data: use week index (1–52 per year); month labels at week numbers that start each month
        if period_col == "week":
            df_ts = df.sort_values(["County", "period_sort"]).copy()
            year_min = df_ts["year"].min()
            df_ts["_x"] = (df_ts["year"] - year_min) * 52 + df_ts["week"]
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            # ISO week-of-year that starts each month (approx): 1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48
            month_start_weeks = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48]
            years = sorted(df_ts["year"].dropna().unique().astype(int))
            tickvals = [(y - year_min) * 52 + w for y in years for w in month_start_weeks]
            ticktext = month_names * len(years) if years else month_names
            x_label = "Month"
        else:
            df_ts = df.sort_values(["County", "period_sort"]).copy()
            df_ts["_x"] = df_ts["period_label"]
            tickvals = ticktext = None
            x_label = "Month"
        ts_vars = [("temp_display", temp_label), ("rh_pct", "Relative humidity (%)"), ("pressure_hpa", "Pressure (hPa)")]
        for var, ylabel in ts_vars:
            if var not in df_ts.columns:
                continue
            fig_ts = px.line(df_ts, x="_x", y=var, color="County", title=ylabel, labels={var: ylabel, "_x": x_label}, color_discrete_map=county_color_map)
            fig_ts = apply_chart_theme(fig_ts, height=320)
            if period_col == "week" and tickvals is not None:
                fig_ts.update_layout(
                    xaxis=dict(
                        tickvals=tickvals, ticktext=ticktext, tickangle=-45,
                        tickfont=dict(size=14, color="#1f2937"),
                        title_font=dict(size=14),
                    ),
                    margin=dict(b=100, r=160),
                )
            else:
                fig_ts.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.warning("Missing weather columns in rollup.")

with tab_dist:
    section_header("Distributions by county (weekly values)", "Box plots of temp, RH, and pressure.")
    dist_vars = [("temp_display" if "temp_display" in df.columns else "temp_c", temp_label), ("rh_pct", "Relative humidity (%)"), ("pressure_hpa", "Pressure (hPa)")]
    for col, label in dist_vars:
        if col not in df.columns:
            continue
        fig_box = px.box(df, x="county_name", y=col, color="County", title=label, labels={col: label, "county_name": "County"}, color_discrete_map=county_color_map)
        fig_box = apply_chart_theme(fig_box, height=320)
        fig_box.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_box, use_container_width=True)

with tab_pue_weather:
    section_header("PUE & WUE vs weather", "How cooling efficiency varies with temperature and humidity.")
    if all(c in df.columns for c in ["temp_c", "AE_PUE", "WEC_PUE", "AE_WUE", "WEC_WUE"]):
        st.caption("Hover for exact values.")
        c1, c2 = st.columns(2)
        temp_x = "temp_display" if "temp_display" in df.columns else "temp_c"
        with c1:
            fig_pue_temp = px.scatter(df, x=temp_x, y="AE_PUE", color="County", symbol="state_abbr", title="AE PUE vs temperature", labels={temp_x: temp_label, "AE_PUE": "AE PUE"}, color_discrete_map=county_color_map)
            fig_pue_temp = apply_chart_theme(fig_pue_temp)
            fig_pue_temp.update_layout(yaxis=dict(autorange=True, fixedrange=False))
            st.plotly_chart(fig_pue_temp, use_container_width=True)
        with c2:
            fig_wec_temp = px.scatter(df, x=temp_x, y="WEC_PUE", color="County", symbol="state_abbr", title="WEC PUE vs temperature", labels={temp_x: temp_label, "WEC_PUE": "WEC PUE"}, color_discrete_map=county_color_map)
            fig_wec_temp = apply_chart_theme(fig_wec_temp)
            fig_wec_temp.update_layout(yaxis=dict(autorange=True, fixedrange=False))
            st.plotly_chart(fig_wec_temp, use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            fig_ae_wue_rh = px.scatter(df, x="rh_pct", y="AE_WUE", color="County", symbol="state_abbr", title="AE WUE vs relative humidity", labels={"rh_pct": "RH (%)", "AE_WUE": "AE WUE"}, color_discrete_map=county_color_map)
            fig_ae_wue_rh = apply_chart_theme(fig_ae_wue_rh)
            fig_ae_wue_rh.update_layout(yaxis=dict(autorange=True, fixedrange=False))
            st.plotly_chart(fig_ae_wue_rh, use_container_width=True)
        with c4:
            fig_wec_wue_rh = px.scatter(df, x="rh_pct", y="WEC_WUE", color="County", symbol="state_abbr", title="WEC WUE vs relative humidity", labels={"rh_pct": "RH (%)", "WEC_WUE": "WEC WUE"}, color_discrete_map=county_color_map)
            fig_wec_wue_rh = apply_chart_theme(fig_wec_wue_rh)
            fig_wec_wue_rh.update_layout(yaxis=dict(autorange=True, fixedrange=False))
            st.plotly_chart(fig_wec_wue_rh, use_container_width=True)
    else:
        st.warning("Rollup missing PUE/WUE or weather columns.")

back_to_top_button()
