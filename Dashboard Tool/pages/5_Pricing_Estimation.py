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
    L_PER_KGAL,
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

# On this page only: add surge-adjusted water cost. comp has base effective_water from comparison_table_with_drought.
if pricing is not None and not pricing.empty and "surge_pct" in pricing.columns:
    comp = comp.merge(
        pricing[["state_abbr", "water_dollars_per_kgal", "surge_pct"]],
        on="state_abbr",
        how="left",
    )
    comp["surge_pct"] = comp["surge_pct"].fillna(0)
    comp["pct_weeks_d2_plus"] = comp["pct_weeks_d2_plus"].fillna(0)
    comp["effective_water_surge"] = (
        (comp["WUE"] / L_PER_KGAL)
        * comp["water_dollars_per_kgal"]
        * (1 + comp["surge_pct"] * comp["pct_weeks_d2_plus"] / 100)
    )
else:
    comp["effective_water_surge"] = comp["effective_water"]

# Annual costs: power and water (surge-adjusted) separately, then total
comp["annual_electric_usd"] = (comp["effective_electric"] / 100) * KWH_PER_YEAR
comp["annual_water_usd"] = comp["effective_water_surge"] * KWH_PER_YEAR
comp["annual_total_usd"] = comp["annual_electric_usd"] + comp["annual_water_usd"]

# ---- Title and assumptions ----
st.markdown("### Pricing estimation")
_static_caption = (
    "This page is where effective utility cost is used: power and water costs are combined into total annual $. "
    "Water uses the full equation: Water = WUE × (Water $/kgal + Penalty), with Penalty = Drought Surge Price × Drought Risk (% time in severe drought). "
    "Electric = PUE × state rate. Not a substitute for utility quotes (e.g. demand charges, TOU)."
)
st.markdown(f'<p style="color: #475569; font-size: 0.875rem; margin-top: -0.5rem;">{_static_caption}</p>', unsafe_allow_html=True)
st.markdown("**Assumptions:** IT load = **100 MW** (constant); hours = **8,760**/year.")

with st.expander("Methodology", expanded=False):
    st.markdown(
        "Effective utility cost (used only on this page) = effective electric + effective water (with drought surge), converted to annual $.\n\n"
        "- Effective electric (¢/kWh IT) = PUE × state electric rate. "
        "Annual electric $ = (effective electric ÷ 100) × 8,760 h × 100 MW.\n"
        "- Effective water (¢/kWh IT) = WUE × (Water $/kgal + Penalty), with Penalty = Drought Surge Price × Drought Risk (Drought risk = % of time in severe drought over last 10 years). "
        "Equivalent form: (WUE / 3785.41) × state water $/kgal × (1 + surge_pct × % severe drought). "
        "Annual water $ = effective water × 8,760 h × 100 MW.\n"
        "- Total annual = annual electric $ + annual water $."
    )

def _fmt_currency(s: pd.Series) -> pd.Series:
    """Format numeric column as currency with commas and $."""
    return s.round(0).apply(lambda x: f"${x:,.0f}")

# ---- Breakdown: Power and water first, then total ----
# Same column order for both: County, system, Effective rate (¢/kWh IT), Annual cost ($) last.
# Each table sorted by its own annual cost metric (lowest first).
section_header("Annual power (electric) cost", "From PUE × state electric rate × 8,760 h × 100 MW.")
st.markdown(
    '<p style="color: #475569; font-size: 0.875rem; margin: 0;"><strong>Effective Power Cost</strong> (¢/kWh IT) = PUE × state electric rate.</p>',
    unsafe_allow_html=True,
)
elec_sorted = comp.sort_values("annual_electric_usd").reset_index(drop=True)
elec_display = elec_sorted[["County", "system", "effective_electric", "annual_electric_usd"]].copy()
elec_display = elec_display.rename(columns={
    "effective_electric": "Effective electric (¢/kWh IT)",
    "annual_electric_usd": "Annual electric ($)",
})
elec_display["Effective electric (¢/kWh IT)"] = elec_display["Effective electric (¢/kWh IT)"].round(4)
elec_display["Annual electric ($)"] = elec_sorted["annual_electric_usd"].values  # keep numeric for gradient
elec_display = elec_display.rename(columns={"system": "System"})
def _make_county_bg(color_map):
    def _apply(x):
        if isinstance(x, pd.Series):
            return x.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}")
        return x.apply(lambda col: col.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}"))
    return _apply
elec_styled = (
    elec_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual electric ($)"], cmap="YlGn_r")  # darker green = lower cost = better
    .format({"Annual electric ($)": lambda x: f"${x:,.0f}"})
)
elec_display_fmt = elec_display.copy()
elec_display_fmt["Annual electric ($)"] = elec_display_fmt["Annual electric ($)"].apply(lambda x: f"${x:,.0f}")
try:
    st.dataframe(elec_styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(elec_display_fmt, use_container_width=True, hide_index=True)

section_header("Annual water cost", "From WUE × state water rate × (1 + drought surge) × 8,760 h × 100 MW.")
st.markdown(
    '<p style="color: #475569; font-size: 0.875rem; margin: 0;"><strong>Effective Water Cost</strong> (¢/kWh IT) = WUE × (Water $/kgal + Penalty), with Penalty = Drought Surge Price × Drought Risk.</p>',
    unsafe_allow_html=True,
)
water_sorted = comp.sort_values("annual_water_usd").reset_index(drop=True)
water_display = water_sorted[["County", "system", "effective_water_surge", "annual_water_usd"]].copy()
water_display["Effective water (¢/kWh IT)"] = (water_display["effective_water_surge"] * 100).round(3)
water_display["Annual water ($)"] = water_sorted["annual_water_usd"].values  # keep numeric for gradient
water_display = water_display[["County", "system", "Effective water (¢/kWh IT)", "Annual water ($)"]]
water_display = water_display.rename(columns={"system": "System"})
water_styled = (
    water_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual water ($)"], cmap="YlGn_r")  # darker green = lower cost = better
    .format({"Annual water ($)": lambda x: f"${x:,.0f}"})
)
water_display_fmt = water_display.copy()
water_display_fmt["Annual water ($)"] = water_display_fmt["Annual water ($)"].apply(lambda x: f"${x:,.0f}")
try:
    st.dataframe(water_styled, use_container_width=True, hide_index=True)
except Exception:
    st.dataframe(water_display_fmt, use_container_width=True, hide_index=True)

section_header("Total annual utility cost")
st.markdown(
    '<p style="color: #475569; font-size: 0.875rem; margin: 0;">Annual electric $ + annual water $.</p>',
    unsafe_allow_html=True,
)
total_sorted = comp.sort_values("annual_total_usd").reset_index(drop=True)
total_display = total_sorted[["County", "system", "annual_electric_usd", "annual_water_usd", "annual_total_usd"]].copy()
total_display = total_display.rename(columns={
    "system": "System",
    "annual_electric_usd": "Annual electric ($)",
    "annual_water_usd": "Annual water ($)",
    "annual_total_usd": "Annual total ($)",
})
# County column = county color; cost columns = green gradient (darker = lower = better)
total_styled = (
    total_display.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Annual electric ($)", "Annual water ($)", "Annual total ($)"], cmap="YlGn_r")
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
