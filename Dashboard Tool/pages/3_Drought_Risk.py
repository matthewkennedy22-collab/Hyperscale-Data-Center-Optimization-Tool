"""Drought risk & mapping: 10-year series, week-of-year pattern, summary by county."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from _utils import render_sidebar, get_drought, get_counties, selected_drought_df, get_county_color_map, lighten_hex, sort_df_by_county_order
from ui import apply_global_css, section_header, apply_chart_theme, metric_row, back_to_top_button, page_top_anchor

st.set_page_config(page_title="Drought risk | County Dashboard", page_icon="•", layout="wide")
apply_global_css()
render_sidebar()
page_top_anchor()

drought = get_drought()
if drought is None:
    st.warning("Drought data not found. Place the drought weekly CSV in the project root, or set **drought_csv_url** in Streamlit secrets (e.g. in Cloud: Manage app → Settings → Secrets).")
    st.caption("Expected: drought_weekly_by_county_2015_2024_week52only.csv (or full weeks 1–52).")
    st.stop()

counties_df = get_counties()
df = selected_drought_df(drought)
if df is None or df.empty:
    st.info("Select one or more counties in the sidebar to view drought risk.")
    st.stop()

if counties_df is not None and not counties_df.empty:
    df = df.merge(counties_df[["county_fips", "county_name", "state_abbr"]].drop_duplicates(), on="county_fips", how="left")
    df["County"] = df["county_name"].fillna("") + ", " + df["state_abbr"].fillna("")
else:
    df["County"] = df["county_fips"]
df = sort_df_by_county_order(df, "County")
_, county_color_map = get_county_color_map()

st.markdown("### Drought risk & patterns")
n_weeks_available = df["week_number"].nunique() if "week_number" in df.columns else 0
st.caption("10-year weekly drought index. 0 = no drought, 5 = exceptional (D4)." + (" Seasonal pattern available (weeks 1–52)." if n_weeks_available >= 2 else " Single week in data — seasonal pattern not shown."))

summary = df.groupby(["county_fips", "County"], as_index=False).agg(
    mean_drought=("drought_level_avg", "mean"),
    max_drought=("drought_level_avg", "max"),
    pct_weeks_d2_plus=("drought_level_avg", lambda s: (s >= 2).mean() * 100),  # severe or worse (D2+)
    n_weeks=("drought_level_avg", "count"),
).round(2)
summary = sort_df_by_county_order(summary, "County")
# Highest and lowest drought risk (insightful, not average)
high_risk = summary.loc[summary["mean_drought"].idxmax()]
low_risk = summary.loc[summary["mean_drought"].idxmin()]
high_label = f"{high_risk['County']} ({high_risk['mean_drought']:.2f})"
low_label = f"{low_risk['County']} ({low_risk['mean_drought']:.2f})"
metric_row([
    (str(len(summary)), "Counties"),
    (high_label[:30] + "…" if len(high_label) > 30 else high_label, "Highest drought risk"),
    (low_label[:30] + "…" if len(low_label) > 30 else low_label, "Lowest drought risk"),
])

# Tabs at top: Risk summary first (Drought risk summary by county)
tab_names = ["Risk summary", "10-year trend"]
if n_weeks_available >= 2:
    tab_names.append("Seasonal pattern")
tab_names.append("Category breakdown")
tabs = st.tabs(tab_names)
tab_sum = tabs[0]
tab_ts = tabs[1]
tab_seasonal = tabs[2] if n_weeks_available >= 2 else None
tab_cat = tabs[-1]

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
    st.dataframe(summary_styled, use_container_width=True, hide_index=True)
    st.download_button("Download summary (CSV)", summary_display.to_csv(index=False).encode("utf-8"), file_name="drought_summary_by_county.csv", mime="text/csv", key="dl_drought_sum")

    # Grouped bar: Mean and Max drought level per county (y-axis not clipped)
    sum_long = summary.melt(id_vars=["County"], value_vars=["mean_drought", "max_drought"], var_name="Metric", value_name="Drought level")
    sum_long["Metric"] = sum_long["Metric"].map({"mean_drought": "Mean (10-yr avg)", "max_drought": "Max (worst week)"})
    fig_summary = px.bar(
        sum_long, x="County", y="Drought level", color="Metric", barmode="group",
        title="Mean and max drought level by county (0 = none, 5 = D4 exceptional)",
        labels={"Drought level": "Drought level"},
        color_discrete_sequence=["#0e7490", "#ea580c"],
        text="Drought level",
    )
    fig_summary.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig_summary = apply_chart_theme(fig_summary)
    y_max = summary["max_drought"].max()
    fig_summary.add_hline(y=2.0, line_dash="dash", line_color="gray", annotation_text="D2 threshold")
    fig_summary.update_layout(
        xaxis_tickangle=-45,
        yaxis=dict(range=[0, max(y_max * 1.08 + 0.1, 2.2)]),
        showlegend=True,
        legend=dict(title="", orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
        margin=dict(b=80, r=160),
    )
    st.plotly_chart(fig_summary, use_container_width=True)

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

with tab_ts:
    section_header("Drought over time (10 years)", "Weekly drought level by county.")
    df_ts = df.sort_values("week_end_date")
    fig_ts = px.line(df_ts, x="week_end_date", y="drought_level_avg", color="County", title="Weekly drought level", labels={"drought_level_avg": "Drought level", "week_end_date": "Week end date"}, color_discrete_map=county_color_map)
    fig_ts = apply_chart_theme(fig_ts, height=420)
    fig_ts.update_layout(legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"))
    st.plotly_chart(fig_ts, use_container_width=True)

    # Category breakdown by year (same table style as Category breakdown tab, for each year in the trend)
    section_header("Drought category breakdown by year", "Percent of county area in each drought category, by year.")
    cat_cols = ["pct_none", "pct_d0", "pct_d1", "pct_d2", "pct_d3", "pct_d4"]
    if "year" in df.columns and all(c in df.columns for c in cat_cols):
        cat_by_year = df.groupby(["County", "year"], as_index=False)[cat_cols].mean().round(1)
        cat_by_year = cat_by_year.rename(columns={"pct_none": "None", "pct_d0": "D0", "pct_d1": "D1", "pct_d2": "D2", "pct_d3": "D3", "pct_d4": "D4"})
        cat_by_year = sort_df_by_county_order(cat_by_year, "County")
        cat_by_year["Year"] = cat_by_year["year"].astype(int)
        display_cat = cat_by_year[["County", "Year", "None", "D0", "D1", "D2", "D3", "D4"]]
        display_cat_styled = display_cat.style.apply(_make_county_bg(county_color_map), subset=["County"])
        st.dataframe(display_cat_styled, use_container_width=True, hide_index=True)
        st.download_button("Download categories by year (CSV)", display_cat.to_csv(index=False).encode("utf-8"), file_name="drought_categories_by_year.csv", mime="text/csv", key="dl_drought_cat_ts")
    else:
        st.caption("Category breakdown by year requires year and category columns (pct_none, pct_d0, …) in the drought data.")

if tab_seasonal is not None:
    with tab_seasonal:
        section_header("Seasonal pattern (by month)", "Average drought by week across available years; axis labeled by month. One line per county.")
        week_avg = df.groupby(["county_fips", "week_number"], as_index=False)["drought_level_avg"].mean().round(3)
        county_label = df.drop_duplicates("county_fips")[["county_fips", "County"]].set_index("county_fips")["County"]
        week_avg["County"] = week_avg["county_fips"].map(county_label)
        week_avg = week_avg.dropna(subset=["County"])
        week_avg = sort_df_by_county_order(week_avg, "County")
        week_avg["_x"] = week_avg["week_number"]
        week_avg = week_avg.sort_values(["County", "_x"]).reset_index(drop=True)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        tickvals = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 48]
        fig_week = px.line(
            week_avg, x="_x", y="drought_level_avg", color="County",
            title="Avg drought over the year (1 line per county)",
            labels={"drought_level_avg": "Avg drought level", "_x": "Month"},
            color_discrete_map=county_color_map,
        )
        fig_week = apply_chart_theme(fig_week, height=320)
        fig_week.update_layout(
            xaxis_title="Month",
            xaxis=dict(
                tickvals=tickvals, ticktext=month_names, tickangle=-45, range=[0.5, 52.5],
                tickfont=dict(size=14, color="#1f2937"),
                title_font=dict(size=14),
            ),
            yaxis=dict(range=[0, None], autorange=True),
            margin=dict(b=100, r=160),
        )
        st.plotly_chart(fig_week, use_container_width=True)

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
            st.dataframe(cat_avg_styled, use_container_width=True, hide_index=True)
            st.download_button("Download categories (CSV)", cat_avg.to_csv(index=False).encode("utf-8"), file_name=f"drought_categories_{int(latest_year)}.csv", mime="text/csv", key="dl_drought_cat")
    else:
        st.info("No year data available for category breakdown.")

back_to_top_button()
