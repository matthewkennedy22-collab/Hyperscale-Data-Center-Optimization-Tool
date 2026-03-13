"""Drought risk comparison: 10-year series, week-of-year pattern, summary by county."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from _utils import render_sidebar, get_drought, get_counties, selected_drought_df, get_county_color_map, lighten_hex, sort_df_by_county_order
from ui import apply_global_css, section_header, apply_chart_theme, metric_row, back_to_top_button, page_top_anchor

st.set_page_config(page_title="Drought risk comparison | County Dashboard", page_icon="•", layout="wide")
apply_global_css()
render_sidebar()
page_top_anchor()

drought = get_drought()
if drought is None:
    if st.session_state.get("drought_url_configured_but_failed"):
        st.error("A drought URL is set in Secrets, but the app could not download the file. For Google Drive: use a direct-download link and share the file with **Anyone with the link**. Then redeploy or refresh.")
    else:
        st.warning("Drought data not found. Place the drought weekly CSV in the project root, or set **drought_csv_url** in Streamlit secrets (Manage app → Settings → Secrets). The app checks secrets automatically when no local file is present.")
    st.caption("Expected: drought_weekly_by_county_2015_2024_week52only.csv (or full weeks 1–52), or the fallback filename _fixed_2.0.csv.")
    st.stop()

counties_df = get_counties()
df = selected_drought_df(drought)
if df is None or df.empty:
    st.info("Select one or more counties in the sidebar to view drought risk comparison.")
    st.stop()

if counties_df is not None and not counties_df.empty:
    df = df.merge(counties_df[["county_fips", "county_name", "state_abbr"]].drop_duplicates(), on="county_fips", how="left")
    df["County"] = df["county_name"].fillna("") + ", " + df["state_abbr"].fillna("")
else:
    df["County"] = df["county_fips"]
df = sort_df_by_county_order(df, "County")
_, county_color_map = get_county_color_map()

st.markdown("### Drought risk comparison & patterns")
st.caption("10-year weekly drought index. 0 = no drought, 5 = exceptional (D4).")

summary = df.groupby(["county_fips", "County"], as_index=False).agg(
    mean_drought=("drought_level_avg", "mean"),
    max_drought=("drought_level_avg", "max"),
    pct_weeks_d2_plus=("drought_level_avg", lambda s: (s >= 2).mean() * 100),  # severe or worse (D2+)
    n_weeks=("drought_level_avg", "count"),
).round(2)
summary = sort_df_by_county_order(summary, "County")

# Tabs at top: Risk summary first (Drought risk summary by county)
tab_names = ["Risk summary", "Category breakdown"]
tabs = st.tabs(tab_names)
tab_sum = tabs[0]
tab_cat = tabs[1]

def _make_county_bg(color_map):
    def _apply(x):
        # Styler passes a Series when subset is one column, DataFrame when multiple
        if isinstance(x, pd.Series):
            return x.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}")
        return x.apply(lambda col: col.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}"))
    return _apply

with tab_sum:
    # Legend: explain drought levels before showing metrics
    st.markdown("**Drought level scale (U.S. Drought Monitor)**")
    st.caption(
        "Drought level uses the U.S. Drought Monitor scale **0–5**: **0** = none, **1** = D1 moderate, **2** = D2 severe, **3** = D3 extreme, **4–5** = D4 exceptional. "
        "**Mean drought level** = average over all weeks in the period; **Max drought level** = worst single week; **% weeks in D2+** = share of weeks with drought ≥ 2 (severe or worse)."
    )
    section_header("Drought risk summary by county", "Mean/max level and % of weeks in D2+ (severe or worse).")
    summary_display = summary.rename(columns={
        "mean_drought": "Mean drought level", "max_drought": "Max drought level",
        "pct_weeks_d2_plus": "% weeks in D2+",
    }).drop(columns=["n_weeks"], errors="ignore")
    summary_styled = summary_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    try:
        st.dataframe(summary_styled, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(summary_display, use_container_width=True, hide_index=True)
    st.download_button("Download summary (CSV)", summary_display.to_csv(index=False).encode("utf-8"), file_name="drought_summary_by_county.csv", mime="text/csv", key="dl_drought_sum")

    # % weeks in D2+ (severe or worse)
    section_header("% of weeks in D2+ (severe or worse)", "Share of 10-year weeks with drought level ≥ 2.")
    fig_pct = px.bar(
        summary, x="County", y="pct_weeks_d2_plus", color="County",
        title="% of weeks in severe drought or worse",
        labels={"pct_weeks_d2_plus": "% weeks in D2+"},
        color_discrete_map=county_color_map,
        text="pct_weeks_d2_plus",
    )
    fig_pct.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_pct = apply_chart_theme(fig_pct)
    y_max_pct = summary["pct_weeks_d2_plus"].max()
    fig_pct.update_layout(
        xaxis_tickangle=-45,
        yaxis_title="% weeks in D2+",
        yaxis=dict(range=[0, max(y_max_pct * 1.25, 15)]),
        margin=dict(t=60, r=160),
    )
    st.plotly_chart(fig_pct, use_container_width=True)

    # Stacked area: percent of county area in U.S. Drought Monitor categories (Risk summary only)
    cat_cols_area = ["pct_none", "pct_d0", "pct_d1", "pct_d2", "pct_d3", "pct_d4"]
    if "week_end_date" in df.columns and all(c in df.columns for c in cat_cols_area):
        section_header("Percent of county area in U.S. Drought Monitor categories", "Each point = one week of drought data. Filled stacked areas (None, D4, D3, D2, D1, D0). Hover for exact values.")
        df_area = df.sort_values(["County", "week_end_date"]).copy()
        df_area["week_end_date"] = pd.to_datetime(df_area["week_end_date"], errors="coerce")
        bands = [
            ("None", ["pct_none"], "#f1f5f9"),
            ("D4", ["pct_none", "pct_d4"], "#8B4513"),
            ("D3", ["pct_none", "pct_d3", "pct_d4"], "#dc2626"),
            ("D2", ["pct_none", "pct_d2", "pct_d3", "pct_d4"], "#ea580c"),
            ("D1", ["pct_none", "pct_d1", "pct_d2", "pct_d3", "pct_d4"], "#fb923c"),
            ("D0", ["pct_none", "pct_d0", "pct_d1", "pct_d2", "pct_d3", "pct_d4"], "#fde047"),
        ]
        for county_label in df_area["County"].unique():
            dc = df_area[df_area["County"] == county_label].dropna(subset=["week_end_date"]).sort_values("week_end_date")
            if dc.empty:
                continue
            x = dc["week_end_date"].tolist()
            fig_area = go.Figure()
            for i, (label, cols, color) in enumerate(bands):
                y = dc[cols].sum(axis=1).clip(upper=100).tolist()
                fig_area.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        name=label,
                        mode="lines",
                        line=dict(width=0, color=color),
                        fill="tonexty" if i > 0 else "tozeroy",
                        fillcolor=color,
                    )
                )
            fig_area.update_layout(
                title=f"{county_label} — Percent area in U.S. Drought Monitor categories",
                xaxis=dict(title="Week end date", type="date", showgrid=True),
                yaxis=dict(title="Percent area", range=[0, 105], ticksuffix="%"),
                hovermode="x unified",
                showlegend=True,
                legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
                margin=dict(t=50, b=80, r=160),
                height=380,
                plot_bgcolor="rgba(248,250,252,0.8)",
            )
            st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.caption("Stacked area charts require *week_end_date* and category columns (pct_none, pct_d0, …) in the drought data.")

with tab_cat:
    latest_year = df["year"].max()
    if pd.notna(latest_year):
        section_header(f"Drought category breakdown (year {int(latest_year)})", "Percent of county area in each drought category.")
        latest = df[df["year"] == latest_year]
        cat_cols = ["pct_none", "pct_d0", "pct_d1", "pct_d2", "pct_d3", "pct_d4"]
        if all(c in latest.columns for c in cat_cols):
            cat_avg = latest.groupby("County", as_index=False)[cat_cols].mean().round(1)
            cat_avg = cat_avg.rename(columns={"pct_none": "None", "pct_d0": "D0", "pct_d1": "D1", "pct_d2": "D2", "pct_d3": "D3", "pct_d4": "D4"})
            cat_avg_styled = cat_avg.style.apply(_make_county_bg(county_color_map), subset=["County"])
            try:
                st.dataframe(cat_avg_styled, use_container_width=True, hide_index=True)
            except Exception:
                st.dataframe(cat_avg, use_container_width=True, hide_index=True)
            st.download_button("Download categories (CSV)", cat_avg.to_csv(index=False).encode("utf-8"), file_name=f"drought_categories_{int(latest_year)}.csv", mime="text/csv", key="dl_drought_cat")
    else:
        st.info("No year data available for category breakdown.")

back_to_top_button()
