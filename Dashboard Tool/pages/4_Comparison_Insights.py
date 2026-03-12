"""Weighted comparison & tailored insights: PUE, WUE, costs, water scarcity."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from _utils import (
    render_sidebar,
    get_rollup,
    get_pricing,
    get_drought,
    get_counties,
    get_drought_summary_by_county,
    comparison_table_with_drought,
    ensure_data,
    get_county_color_map,
    lighten_hex,
)
from ui import apply_global_css, section_header, apply_chart_theme, metric_row, back_to_top_button, page_top_anchor, SYSTEM_PATTERN_MAP, SYSTEM_SYMBOL_MAP

st.set_page_config(page_title="Comparison insights | County Dashboard", page_icon="•", layout="wide")
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
    st.info("Select one or more counties in the sidebar to see weighted comparison and insights.")
    st.stop()

comp = comp.copy()
# Display water cost in cents (¢/kWh IT) for readability
comp["effective_water_cents"] = (comp["effective_water"] * 100).round(3)
# Normalize 0–1 for composite (higher raw cost = worse). Flipped and scaled to 0–100 so higher score = better.
for col in ["effective_electric", "effective_water", "water_stress"]:
    cmin, cmax = comp[col].min(), comp[col].max()
    if cmax > cmin:
        comp[f"{col}_n"] = (comp[col] - cmin) / (cmax - cmin)
    else:
        comp[f"{col}_n"] = 0.0

# ---- Page title & balance slider (top level) ----
st.markdown("### Comparison insights")
st.caption("Compare counties and cooling systems (AE vs WEC) by power cost, water cost, and water scarcity. Use the slider to weight power vs water, then explore the summary and dive into each area below.")

# Dropdown above slider: how calculations work and how weighting affects composite
with st.expander("How calculations work & how weighting affects the composite score", expanded=False):
    st.markdown("""
**Composite uses separate PUE and WUE terms** — we do **not** merge them into an \"effective utility cost.\" That combined cost (with full water equation including drought penalty) is used only on **Pricing Estimation** for total annual $.

**Inputs (per county × cooling system), each normalized then weighted:**
- **Electric** (PUE-based): PUE × state electric rate → ¢/kWh IT. Lower is better.
- **Water cost** (WUE-based, **base only**): WUE × state water $/kgal → ¢/kWh IT. No drought surge here. For cost with surge, see **Pricing Estimation**.
- **Water stress** (WUE-based): *How risky is this location's water future?* — WUE × (1 + % of time in severe drought, D2–D4). Lower is better.

**Normalization:** For your selected counties and systems, each of these three is scaled to 0–1: the best (lowest) value becomes 0, the worst (highest) becomes 1. So every row has three normalized scores: electric_n, water_n, water_stress_n.

**Composite score equation:**
```
composite = (w_electric × electric_n + w_water × water_n + w_drought × water_stress_n) / total_weight
```
where `total_weight = w_electric + w_water + w_drought` (always 1). Power weight = w_electric; water weight = w_water + w_drought (base water cost and water stress).

**How the slider (Power ↔ Water) affects it:**
- **Power (left):** 100% power, 0% water → only electric cost matters. Best fit = lowest effective electric cost.
- **Water (right):** 0% power, 100% water → only water cost and drought matter. Best fit = lowest water cost and water stress.
- **Middle (balanced):** 50% power, 50% water → electric and (water cost + drought) weighted equally; within water, cost and drought each get half. Best fit = best average across both sides.

**Higher composite = better overall fit** (score 0–100) for your chosen weighting. Rankings update as you move the slider.
""")

st.markdown("**Set your priority:** Drag the slider to favor **Power** (electric cost only), **Water** (water cost + drought), or a balance. The composite score and rankings below update as you move it.")
st.caption("Left = power matters most · Center = balanced · Right = water matters most")

# Slider styling: highlighted container, neutral track, thumb visible
st.markdown("""
<style>
  [data-testid="stSlider"] [data-baseweb="slider"] { background: #e2e8f0 !important; }
  [data-testid="stSlider"] [data-baseweb="slider"] > div:first-of-type { background: #e2e8f0 !important; }
  [data-testid="stSlider"] {
    border: 2px solid #3b82f6;
    border-radius: 10px;
    padding: 14px 16px;
    background: #eff6ff !important;
  }
  [data-testid="stSlider"] [role="slider"],
  [data-testid="stSlider"] [data-baseweb="thumb"] { background: #3b82f6 !important; }
  [data-testid="stSlider"] [data-baseweb="slider"] > div:first-child:not([role="slider"]):not([data-baseweb="thumb"]),
  [data-testid="stSlider"] [data-baseweb="slider"] > div:last-child:not([role="slider"]):not([data-baseweb="thumb"]) { font-size: 0 !important; color: transparent !important; }
</style>
""", unsafe_allow_html=True)
# Slider -1 to 1 with 0 in middle; tick scale below
slider_col1, slider_col2, slider_col3 = st.columns([1, 3, 1])
with slider_col1:
    st.markdown("<div style='text-align: right; padding-top: 0.5rem;'><strong>Power</strong></div>", unsafe_allow_html=True)
with slider_col2:
    balance_raw = st.slider(
        "Weight power vs water",
        -1.0, 1.0, 0.0, 0.25,
        label_visibility="collapsed",
        help="Drag to weight Power (left) or Water (right). 0 = balanced.",
        key="power_water_balance",
    )
    balance = (balance_raw + 1.0) / 2.0
with slider_col3:
    st.markdown("<div style='padding-top: 0.5rem;'><strong>Water</strong></div>", unsafe_allow_html=True)
# Tick marks with 0 in middle, points moving outward (-1, -0.5, 0, 0.5, 1)
_, scale_col, _ = st.columns([1, 3, 1])
with scale_col:
    st.markdown("""
    <style>
      .balance-scale { display: flex; justify-content: space-between; align-items: flex-end; width: 100%; padding: 4px 0 0; }
      .balance-tick { display: flex; flex-direction: column; align-items: center; flex: 0 0 auto; }
      .balance-tick .tick-bar { width: 2px; background: #64748b; border-radius: 1px; }
      .balance-tick .tick-major { height: 10px; }
      .balance-tick .tick-minor { height: 5px; }
      .balance-tick .tick-label { font-size: 0.7rem; color: #475569; font-weight: 600; margin-top: 2px; }
    </style>
    <div class="balance-scale">
      <div class="balance-tick"><span class="tick-bar tick-major"></span><span class="tick-label">−1</span></div>
      <div class="balance-tick"><span class="tick-bar tick-minor"></span><span class="tick-label"></span></div>
      <div class="balance-tick"><span class="tick-bar tick-major"></span><span class="tick-label">−0.5</span></div>
      <div class="balance-tick"><span class="tick-bar tick-minor"></span><span class="tick-label"></span></div>
      <div class="balance-tick"><span class="tick-bar tick-major"></span><span class="tick-label">0</span></div>
      <div class="balance-tick"><span class="tick-bar tick-minor"></span><span class="tick-label"></span></div>
      <div class="balance-tick"><span class="tick-bar tick-major"></span><span class="tick-label">0.5</span></div>
      <div class="balance-tick"><span class="tick-bar tick-minor"></span><span class="tick-label"></span></div>
      <div class="balance-tick"><span class="tick-bar tick-major"></span><span class="tick-label">1</span></div>
    </div>
    """, unsafe_allow_html=True)
# Weights: power (electric) vs water (water cost + drought). Middle = 50/50.
w_electric = (1.0 - balance)
w_water = balance / 2.0   # half of "water" side
w_drought = balance / 2.0
total_w = w_electric + w_water + w_drought  # = 1.0 so middle is exactly 50/50
if total_w <= 0:
    total_w = 1.0
# Caption: power % and water % (water = cost + drought), accurate for each slider point
pct_power_cap = (w_electric / total_w * 100) if total_w > 0 else 0
pct_water_cap = ((w_water + w_drought) / total_w * 100) if total_w > 0 else 0
if balance <= 0.2:
    label_cap = "**Power** (electric cost weighted most)"
elif balance >= 0.8:
    label_cap = "**Water** (water cost and drought weighted most)"
else:
    label_cap = "**Balanced** (power, water cost, and drought weighted equally)"
st.caption(f"Current: {label_cap} — {pct_power_cap:.0f}% power, {pct_water_cap:.0f}% water")
# Raw composite: lower = better (0-1). Flip and scale to 0-100 so higher = better.
_raw_composite = (
    w_electric * comp["effective_electric_n"]
    + w_water * comp["effective_water_n"]
    + w_drought * comp["water_stress_n"]
) / total_w
comp["composite"] = (1.0 - _raw_composite) * 100.0  # 0-100, higher = better

# Sort by composite (best first) and add rank for overview
comp_sorted = comp.sort_values("composite", ascending=False).reset_index(drop=True)
comp_sorted["Rank"] = range(1, len(comp_sorted) + 1)
ordered_labels, county_color_map = get_county_color_map()

# ---- Composite score ranking (overview at top) ----
section_header("Composite score ranking", "County × system ranked by composite score (higher = better fit for your Power ↔ Water setting).")
comp_chart = comp_sorted.iloc[::-1].reset_index(drop=True)  # reverse so best (Rank 1) appears at top of chart
comp_chart["County × System"] = comp_chart["County"] + " — " + comp_chart["system"]
fig_rank = px.bar(
    comp_chart,
    x="composite",
    y="County × System",
    color="County",
    orientation="h",
    title="Ranking by composite score (1 = best)",
    labels={"composite": "Composite score", "County × System": ""},
    color_discrete_map=county_color_map,
    text="composite",
)
fig_rank.update_traces(texttemplate="%{text:.1f}", textposition="outside")
fig_rank = apply_chart_theme(fig_rank, height=max(280, len(comp_chart) * 36))
fig_rank.update_layout(showlegend=True, legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"), yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_rank, use_container_width=True)

# ---- Comparison table (breakdown, ordered by composite) ----
section_header("Comparison table", "PUE, WUE, effective costs (¢/kWh IT), drought, water stress. **Eff. water (base)** = base cost comparison (no surge); **Water stress** = how risky is this location's water future? Sorted by composite score (best first). Darker green = better composite. For cost including drought surcharges, see Pricing Estimation.")
display_cols = ["Rank", "County", "system", "PUE", "WUE", "effective_electric", "effective_water_cents", "mean_drought", "pct_weeks_d2_plus", "water_stress", "composite"]
display_df = comp_sorted[display_cols].copy()
display_df = display_df.rename(columns={
    "system": "System",
    "effective_electric": "Eff. electric (¢/kWh IT)",
    "effective_water_cents": "Eff. water (base ¢/kWh IT)",
    "mean_drought": "Mean drought (0–5)",
    "pct_weeks_d2_plus": "% weeks severe (D2–D4)",
    "water_stress": "Water stress",
    "composite": "Composite score",
})
display_df = display_df.round(4)
if "Rank" in display_df.columns:
    display_df["Rank"] = display_df["Rank"].astype(int)
if "Composite score" in display_df.columns:
    display_df["Composite score"] = display_df["Composite score"].round(1)
# County column: filled with county color (same as sidebar); Composite score: green gradient (darker = better, like Pricing Estimation)
def _make_county_bg(color_map):
    def _apply(x):
        # Styler passes a Series when subset is one column, DataFrame when multiple
        if isinstance(x, pd.Series):
            return x.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}")
        return x.apply(lambda col: col.map(lambda v: f"background-color: {lighten_hex(color_map.get(v, '#ddd'))}"))
    return _apply
display_styled = (
    display_df.style.apply(_make_county_bg(county_color_map), subset=["County"])
    .background_gradient(subset=["Composite score"], cmap="YlGn")  # higher = greener = better
)
try:
    st.dataframe(display_styled, use_container_width=True, hide_index=True)
except Exception:
    # Fallback: some Streamlit/Arrow environments raise ImportError on styled dataframes
    st.dataframe(display_df, use_container_width=True, hide_index=True)
st.download_button("Download comparison (CSV)", display_df.to_csv(index=False).encode("utf-8"), file_name="comparison_insights.csv", mime="text/csv", key="dl_insights")

# ---- Dive into: Power (electric cost) ----
st.markdown("---")
section_header("Power: effective electric cost", "PUE × state electric rate → ¢/kWh IT. Lower is better.")
# Cost comparison electric part (electric vs water bars) - show electric first in a compact way
cost_long = comp.melt(
    id_vars=["County", "system"],
    value_vars=["effective_electric", "effective_water_cents"],
    var_name="Cost type",
    value_name="Value",
)
cost_long["Cost type"] = cost_long["Cost type"].map({"effective_electric": "Electric (¢/kWh IT)", "effective_water_cents": "Water (¢/kWh IT)"})
fig_cost = px.bar(
    cost_long,
    x="County",
    y="Value",
    color="County",
    pattern_shape="system",
    facet_row="Cost type",
    barmode="group",
    title="Effective electric and water cost by county and system",
    labels={"Value": "Effective cost"},
    color_discrete_map=county_color_map,
    pattern_shape_map=SYSTEM_PATTERN_MAP,
)
fig_cost = apply_chart_theme(fig_cost)
fig_cost.update_layout(xaxis_tickangle=-45)
# Remove facet row annotations (unreadable vertical "Cost type" label)
fig_cost.for_each_annotation(lambda a: a.update(text=""))
st.plotly_chart(fig_cost, use_container_width=True)

# ---- Dive into: Water (cost & scarcity) ----
st.markdown("---")
section_header("Water: cost and scarcity (drought)", "**Effective water cost (base)** = base cost comparison (no surge). **Water stress** = *how risky is this location's water future?* — WUE × (1 + % time in severe drought, D2–D4); forward-looking scarcity risk. Lower is better. For cost including drought surcharges, see Pricing Estimation.")
# Water stress bar chart
fig_ws = px.bar(
    comp,
    x="County",
    y="water_stress",
    color="County",
    pattern_shape="system",
    barmode="group",
    title="Water stress (sustainability / scarcity risk) by county and system",
    labels={"water_stress": "Water stress (WUE × drought exposure)", "system": "System"},
    color_discrete_map=county_color_map,
    pattern_shape_map=SYSTEM_PATTERN_MAP,
)
fig_ws = apply_chart_theme(fig_ws)
fig_ws.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_ws, use_container_width=True)

# ---- Composite score ----
st.markdown("---")
section_header("Composite score", "Single weighted score (0–100) combining power cost, water cost, and water scarcity. **Higher = better fit** for your Power ↔ Water setting above.")
# How it's built (current weights)
total_w = w_electric + w_water + w_drought
pct_power = (w_electric / total_w * 100) if total_w > 0 else 0
pct_water = ((w_water + w_drought) / total_w * 100) if total_w > 0 else 0
st.markdown(
    f"The composite uses **normalized** electric cost, water cost, and water stress (drought). "
    f"With your current slider: **{pct_power:.0f}%** weight on power (electric cost), **{pct_water:.0f}%** on water (water cost + drought). "
    "Each factor is scaled 0–1; the weighted average is inverted and scaled to 0–100 so higher = better."
)
with st.expander("How the composite is calculated", expanded=False):
    st.markdown(
        "- **Electric:** Effective electric cost (¢/kWh IT) = PUE × state rate. Normalized so the worst county×system in your selection = 1.\n"
        "- **Water cost (base):** Effective water cost at base rates (no drought surge). Normalized the same way. For cost including surcharges, see Pricing Estimation.\n"
        "- **Water stress:** *How risky is this location's water future?* — WUE × (1 + % of time in severe drought, D2–D4). Forward-looking scarcity risk. Normalized the same way.\n"
        "- **Weights:** Power slider sets how much to favor power vs water. Composite = 100 × (1 − weighted average of normalized costs). Score 0–100; higher = better overall fit."
    )

# Ranking chart: Rank on x-axis; color = county, pattern = system (solid AE, striped WEC)
st.markdown("**Ranking** — Best (highest composite) to worst (lowest).")
fig_comp = px.bar(
    comp_sorted,
    x="Rank",
    y="composite",
    color="County",
    pattern_shape="system",
    hover_data=["County", "PUE", "WUE", "effective_electric", "effective_water_cents", "mean_drought", "water_stress"],
    title="Composite score rank (higher is better, out of 100)",
    labels={"composite": "Composite score", "Rank": "Rank"},
    color_discrete_map=county_color_map,
    pattern_shape_map=SYSTEM_PATTERN_MAP,
)
fig_comp = apply_chart_theme(fig_comp)
st.plotly_chart(fig_comp, use_container_width=True)

# Tailored insights (inside Composite section)
section_header("Tailored insights", "Summary based on your selected counties, systems, and current Power ↔ Water weight.")
insights = []

# Best/worst by composite (comp_sorted is best-first, so iloc[0] = best, iloc[-1] = worst)
best = comp_sorted.iloc[0]
insights.append(f"**Best overall (highest composite):** {best['County']} — **{best['system']}** (score {best['composite']:.1f}/100).")
worst = comp_sorted.iloc[-1]
insights.append(f"**Worst overall (lowest composite):** {worst['County']} — **{worst['system']}** (score {worst['composite']:.1f}/100).")

# Drought and water stress
high_drought = comp[comp["mean_drought"] >= 1.0]
if not high_drought.empty:
    ae_ws = high_drought[high_drought["system"] == "AE"]["water_stress"].mean()
    wec_ws = high_drought[high_drought["system"] == "WEC"]["water_stress"].mean()
    if wec_ws > ae_ws * 1.05:
        insights.append(f"In **high-drought counties** (mean drought ≥ 1), **AE** has lower average water stress ({ae_ws:.2f}) than **WEC** ({wec_ws:.2f}) — AE may be preferable where water is scarce.")
    elif ae_ws > wec_ws * 1.05:
        insights.append(f"In **high-drought counties**, **WEC** has lower average water stress ({wec_ws:.2f}) than **AE** ({ae_ws:.2f}).")
else:
    insights.append("Drought levels are low in selected counties; water stress is driven mainly by WUE and water cost.")

# Electric cost spread
try:
    if comp["effective_electric"].max() > comp["effective_electric"].min() * 1.1:
        cheap = comp.loc[comp["effective_electric"].idxmin()]
        insights.append(f"**Lowest effective electric cost:** {cheap['County']} — **{cheap['system']}** ({cheap['effective_electric']:.2f} ¢/kWh).")
except Exception:
    pass
# Water cost spread
try:
    if comp["effective_water_cents"].max() > comp["effective_water_cents"].min() * 1.1:
        cheap_w = comp.loc[comp["effective_water_cents"].idxmin()]
        insights.append(f"**Lowest effective water cost:** {cheap_w['County']} — **{cheap_w['system']}** ({cheap_w['effective_water_cents']:.2f} ¢/kWh IT).")
except Exception:
    pass

for line in insights:
    st.markdown(f"- {line}")

back_to_top_button()
