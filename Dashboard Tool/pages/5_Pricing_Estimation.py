"""Pricing estimation: annual utility cost for a fixed 100 MW hyperscale IT load."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from _utils import (
    render_sidebar,
    get_rollup,
    get_pricing,
    get_drought,
    get_drought_summary_by_county,
    comparison_table_with_drought,
    ensure_data,
    get_county_color_map,
    lighten_hex,
    sort_df_by_county_order,
)
from ui import apply_global_css, section_header, apply_chart_theme, back_to_top_button, page_top_anchor, PLOTLY_LAYOUT

# Fixed for this page: 100 MW hyperscale IT load
IT_LOAD_MW = 100
HOURS_PER_YEAR = 8760
KW = IT_LOAD_MW * 1000  # 100,000 kW
KWH_PER_YEAR = KW * HOURS_PER_YEAR  # 8.76e9 kWh IT/year

st.set_page_config(page_title="Pricing estimation | County Dashboard", page_icon="•", layout="wide")
apply_global_css()
render_sidebar()
page_top_anchor()
ensure_data()

rollup = get_rollup()
pricing = get_pricing()
drought = get_drought()
drought_summary = get_drought_summary_by_county(drought) if drought is not None else None
comp = comparison_table_with_drought(rollup, pricing, drought_summary)

if comp is None or comp.empty:
    st.info("Select one or more counties in the sidebar to see pricing estimates.")
    st.stop()

comp = sort_df_by_county_order(comp.copy(), "County")
_, county_color_map = get_county_color_map()

# Annual costs: power and water separately, then total
# effective_electric = ¢/kWh IT, effective_water = $/kWh IT
comp["annual_electric_usd"] = (comp["effective_electric"] / 100) * KWH_PER_YEAR
comp["annual_water_usd"] = comp["effective_water"] * KWH_PER_YEAR
comp["annual_total_usd"] = comp["annual_electric_usd"] + comp["annual_water_usd"]

# ---- Title and assumptions ----
st.markdown("### Pricing estimation (100 MW IT load)")
st.caption(
    "Estimated annual utility cost for comparison across counties and cooling systems. "
    "Uses state-level electric and water rates; PUE and WUE are annual averages. "
    "Water cost may include a **drought surge** (state surge % × county % time in severe drought) when surge and drought data are available. "
    "Not a substitute for utility quotes (e.g. demand charges, TOU)."
)
st.markdown("**Assumptions:** IT load = **100 MW** (constant); hours = **8,760**/year.")

with st.expander("Methodology", expanded=False):
    st.markdown(
        "- **Effective electric** (¢/kWh IT) = PUE × state electric rate. "
        "Annual electric $ = (effective electric ÷ 100) × 8,760 h × 100 MW.\n"
        "- **Effective water** ($/kWh IT) = (WUE / 3785.41) × state water $/kgal × (1 + surge_pct × % severe drought). "
        "This is **economic cost** (what you pay); when surge and drought data exist, it includes a drought surge. "
        "Annual water $ = effective water × 8,760 h × 100 MW. For **sustainability / scarcity risk** (water stress), see Comparison Insights.\n"
        "- **Total annual** = annual electric $ + annual water $."
    )

def _fmt_currency(s: pd.Series) -> pd.Series:
    """Format numeric column as currency with commas and $."""
    return s.round(0).apply(lambda x: f"${x:,.0f}")

# ---- Breakdown: Power and water first, then total ----
# Same column order for both: County, system, Effective rate (¢/kWh IT), Annual cost ($) last.
# Each table sorted by its own annual cost metric (lowest first).
section_header("Annual power (electric) cost", "From PUE × state electric rate × 8,760 h × 100 MW.")
elec_sorted = comp.sort_values("annual_electric_usd").reset_index(drop=True)
elec_display = elec_sorted[["County", "system", "effective_electric", "annual_electric_usd"]].copy()
elec_display = elec_display.rename(columns={
    "effective_electric": "Effective electric (¢/kWh IT)",
    "annual_electric_usd": "Annual electric ($)",
})
elec_display["Effective electric (¢/kWh IT)"] = elec_display["Effective electric (¢/kWh IT)"].round(4)
elec_display["Annual electric ($)"] = elec_sorted["annual_electric_usd"].values  # keep numeric for gradient
def _make_county_bg(color_map):
    def _apply(x):
        # Styler passes a Series when subset is one column, DataFrame when multiple
        if isinstance(x, pd.Series):
            return x.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}")
        return x.apply(lambda col: col.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}"))
    return _apply
elec_styled = (
    elec_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual electric ($)"], cmap="YlGn_r")
    .format({"Annual electric ($)": lambda x: f"${x:,.0f}"})
)
elec_display_fmt = elec_display.copy()
elec_display_fmt["Annual electric ($)"] = elec_display_fmt["Annual electric ($)"].apply(lambda x: f"${x:,.0f}")
try:
    st.dataframe(elec_styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(elec_display_fmt, use_container_width=True, hide_index=True)

section_header("Annual water cost", "From WUE × state water rate × 8,760 h × 100 MW.")
water_sorted = comp.sort_values("annual_water_usd").reset_index(drop=True)
water_display = water_sorted[["County", "system", "effective_water", "annual_water_usd"]].copy()
water_display["Effective water (¢/kWh IT)"] = (water_display["effective_water"] * 100).round(3)
water_display["Annual water ($)"] = water_sorted["annual_water_usd"].values  # keep numeric for gradient
water_display = water_display[["County", "system", "Effective water (¢/kWh IT)", "Annual water ($)"]]
water_styled = (
    water_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual water ($)"], cmap="YlGn_r")
    .format({"Annual water ($)": lambda x: f"${x:,.0f}"})
)
water_display_fmt = water_display.copy()
water_display_fmt["Annual water ($)"] = water_display_fmt["Annual water ($)"].apply(lambda x: f"${x:,.0f}")
try:
    st.dataframe(water_styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(water_display_fmt, use_container_width=True, hide_index=True)

section_header("Total annual utility cost", "Annual electric $ + annual water $.")
total_sorted = comp.sort_values("annual_total_usd").reset_index(drop=True)
total_display = total_sorted[["County", "system", "annual_electric_usd", "annual_water_usd", "annual_total_usd"]].copy()
total_display = total_display.rename(columns={
    "annual_electric_usd": "Annual electric ($)",
    "annual_water_usd": "Annual water ($)",
    "annual_total_usd": "Annual total ($)",
})
# Keep numeric for gradient on last column; format all cost columns as currency
total_styled = (
    total_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual total ($)"], cmap="YlGn_r")
    .format({
        "Annual electric ($)": lambda x: f"${x:,.0f}",
        "Annual water ($)": lambda x: f"${x:,.0f}",
        "Annual total ($)": lambda x: f"${x:,.0f}",
    })
)
total_display_fmt = total_display.copy()
for c in ["Annual electric ($)", "Annual water ($)", "Annual total ($)"]:
    total_display_fmt[c] = total_display_fmt[c].apply(lambda x: f"${x:,.0f}")
try:
    st.dataframe(total_styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(total_display_fmt, use_container_width=True, hide_index=True)
# Download with numeric values (no $/commas) for CSV; use total-order for download
total_download = total_sorted[["County", "system", "annual_electric_usd", "annual_water_usd", "annual_total_usd"]].copy()
total_download = total_download.rename(columns={
    "annual_electric_usd": "Annual electric ($)",
    "annual_water_usd": "Annual water ($)",
    "annual_total_usd": "Annual total ($)",
})
for c in ["Annual electric ($)", "Annual water ($)", "Annual total ($)"]:
    total_download[c] = total_download[c].round(0)
st.download_button(
    "Download pricing estimation (CSV)",
    total_download.to_csv(index=False).encode("utf-8"),
    file_name="pricing_estimation_100MW.csv",
    mime="text/csv",
    key="dl_pricing_est",
)

# ---- Stacked bar: one bar per county × system, colored by county; power bottom (solid), water on top (striped) ----
# Bar order matches Total annual utility cost table (by annual_total_usd)
section_header("Annual cost by county and system", "Stacked: Power (bottom) + Water (top) = total. Color = county (see axis); legend = cost type only.")
bar_comp = total_sorted.copy()
bar_comp["County × System"] = bar_comp["County"] + " — " + bar_comp["system"]
x_cats = bar_comp["County × System"].tolist()
n = len(bar_comp)
# Build one trace per (County, cost type) so we can stack and color by county
fig = go.Figure()
# Power traces first (bottom of stack), then Water (top)
for cost_type, pattern_shape in [("Power (electric)", ""), ("Water", "/")]:
    y_col = "annual_electric_usd" if cost_type == "Power (electric)" else "annual_water_usd"
    first_in_group = True
    for _, row in bar_comp.iterrows():
        county = row["County"]
        color = county_color_map.get(county, "#888")
        y_vals = [bar_comp.iloc[i][y_col] if bar_comp.iloc[i]["County"] == county else 0 for i in range(n)]
        bar_kw = dict(
            x=x_cats,
            y=y_vals,
            name=cost_type,
            legendgroup=cost_type,
            marker_color=color,
            hovertemplate="%{x}<br>" + cost_type + ": $%{y:,.0f}<extra></extra>",
            showlegend=first_in_group,
        )
        if pattern_shape:
            bar_kw["marker_pattern_shape"] = pattern_shape
        fig.add_trace(go.Bar(**bar_kw))
        first_in_group = False
_layout = {k: v for k, v in PLOTLY_LAYOUT.items() if k not in ("legend", "xaxis", "height", "margin")}
fig.update_layout(
    **_layout,
    barmode="stack",
    title="Annual utility cost breakdown (100 MW IT load)",
    xaxis_title="County × System",
    yaxis_title="Annual cost ($)",
    xaxis=dict(tickangle=-45, type="category", categoryorder="array", categoryarray=x_cats),
    height=380,
    legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", font=dict(size=10)),
    margin=dict(l=60, r=140, t=50, b=100),
)
st.plotly_chart(fig, use_container_width=True)

back_to_top_button()
