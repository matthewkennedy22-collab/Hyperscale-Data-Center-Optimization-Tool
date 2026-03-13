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
# Add state-level rates (before PUE/WUE) so table can show how cost affects composite
if pricing is not None and not pricing.empty:
    comp = comp.merge(
        pricing[["state_abbr", "electric_cents_per_kwh", "water_dollars_per_kgal"]],
        on="state_abbr",
        how="left",
    )
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

# Dropdown above slider: how the composite is calculated
with st.expander("How the composite is calculated", expanded=False):
    st.markdown("""
- **Electric:** PUE × state rate → ¢/kWh IT.
- **Water (base):** WUE × state water $/kgal at base rates (no surge). For cost including surcharges, see Pricing Estimation.
- **Water stress risk:** *How risky is this location's water future?* — WUE × (1 + % of time in severe drought, D2–D4).

**Normalization:** For each metric, we scale to 0–1 within your selection: **best** (lowest) = 0, **worst** (highest) = 1. So a higher normalized value means worse.

**Composite:** 100 × (1 − weighted average of those normalized scores). So **higher composite = better** overall fit (0–100). The Power slider sets the weights.
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
comp_chart = comp_sorted.copy()
comp_chart["County × System"] = comp_chart["County"] + " — " + comp_chart["system"]
# Fix y-axis order: rank 1 (best) at top, worst at bottom
y_order = comp_chart["County × System"].tolist()
fig_rank = px.bar(
    comp_chart,
    x="composite",
    y="County × System",
    color="County",
    pattern_shape="system",
    orientation="h",
    title="Ranking by composite score",
    labels={"composite": "Composite score", "County × System": ""},
    color_discrete_map=county_color_map,
    pattern_shape_map=SYSTEM_PATTERN_MAP,
    text="composite",
)
fig_rank.update_traces(texttemplate="%{text:.1f}", textposition="outside")
fig_rank = apply_chart_theme(fig_rank, height=max(280, len(comp_chart) * 36))
fig_rank.update_layout(
    showlegend=True,
    legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
    yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=y_order),
)
st.plotly_chart(fig_rank, use_container_width=True)

# ---- Comparison table (breakdown, ordered by composite) ----
section_header("Comparison table", "Rank, county, system, PUE, WUE, electric rate, water rate, % weeks severe, and composite score.")
display_cols = ["Rank", "County", "system", "PUE", "WUE", "electric_cents_per_kwh", "water_dollars_per_kgal", "pct_weeks_d2_plus", "composite"]
# Only include rate columns if we have them (pricing merged)
if "electric_cents_per_kwh" not in comp_sorted.columns or "water_dollars_per_kgal" not in comp_sorted.columns:
    display_cols = [c for c in display_cols if c not in ("electric_cents_per_kwh", "water_dollars_per_kgal")]
display_df = comp_sorted[[c for c in display_cols if c in comp_sorted.columns]].copy()
display_df = display_df.rename(columns={
    "system": "System",
    "electric_cents_per_kwh": "Electric rate (¢/kWh)",
    "water_dollars_per_kgal": "Water rate ($/kgal)",
    "pct_weeks_d2_plus": "% weeks severe (D2–D4)",
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

# ---- Tailored insights ----
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
        insights.append(f"In **high-drought counties** (mean drought ≥ 1), **AE** has lower average water stress risk ({ae_ws:.2f}) than **WEC** ({wec_ws:.2f}) — AE may be preferable where water is scarce.")
    elif ae_ws > wec_ws * 1.05:
        insights.append(f"In **high-drought counties**, **WEC** has lower average water stress risk ({wec_ws:.2f}) than **AE** ({ae_ws:.2f}).")
else:
    insights.append("Drought levels are low in selected counties; water stress risk is driven mainly by WUE.")

# Electric cost spread
try:
    if comp["effective_electric"].max() > comp["effective_electric"].min() * 1.1:
        cheap = comp.loc[comp["effective_electric"].idxmin()]
        insights.append(f"**Lowest electric cost:** {cheap['County']} — **{cheap['system']}** ({cheap['effective_electric']:.2f} ¢/kWh).")
except Exception:
    pass
# Water cost spread
try:
    if comp["effective_water_cents"].max() > comp["effective_water_cents"].min() * 1.1:
        cheap_w = comp.loc[comp["effective_water_cents"].idxmin()]
        insights.append(f"**Lowest water cost (base):** {cheap_w['County']} — **{cheap_w['system']}** ({cheap_w['effective_water_cents']:.2f} ¢/kWh IT).")
except Exception:
    pass

for line in insights:
    st.markdown(f"- {line}")

back_to_top_button()
