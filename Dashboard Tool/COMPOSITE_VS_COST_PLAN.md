# Composite (Comparison Insights) vs Cost (Pricing Estimation) — Plan

## Goal

- **Composite score** = overall drought/site risk and efficiency, using **base** water cost + **water stress**. No surge.
- **Pricing Estimation** = expected dollar cost, including **drought surge** in water cost.
- **Presentation** = Make the two roles explicit: "How risky is this location's water future?" (water stress) vs "What will water cost us today given known pricing and surcharges?" (effective water cost with surge).

---

## 1. Two metrics, two jobs (explicit framing)

| Metric | Question it answers | Where used | Formula |
|--------|--------------------|------------|--------|
| **Water stress** | "How risky is this location's water future?" — physical/regulatory scarcity risk; forward-looking. Unitless. | Comparison Insights (composite + table) | WUE × (1 + % severe drought) |
| **Effective water cost** (base) | Base water cost for comparison (no surge). | Comparison Insights (composite + table), System Comparison | (WUE / 3785.41) × water $/kgal |
| **Effective water cost (with surge)** | "What will water cost us today given known pricing and drought surcharges?" | Pricing Estimation only | (WUE / 3785.41) × water $/kgal × (1 + surge_pct × % severe) |

---

## 2. Code changes

### 2.1 `_utils.comparison_table_with_drought`

- **Effective water:** Compute **base only** (no surge). Remove the `water_mult = 1 + surge_pct * pct_weeks_d2_plus/100` and set:
  - `effective_water_AE` = (AE_WUE / L_PER_KGAL) × water_dollars_per_kgal  
  - `effective_water_WEC` = (WEC_WUE / L_PER_KGAL) × water_dollars_per_kgal  
- **Water stress** unchanged: WUE × (1 + pct_severe/100).
- No need to merge or use `surge_pct` in this function.

Result: Comparison Insights composite and table use base water + water stress; no surge in composite.

### 2.2 `_utils.selected_counties_df`

- **Effective water:** Always **base only**. Remove the branch that applies surge when `drought_summary` is present. Always:
  - `effective_water_AE` = (AE_WUE / L_PER_KGAL) × water_dollars_per_kgal  
  - `effective_water_WEC` = (WEC_WUE / L_PER_KGAL) × water_dollars_per_kgal  
- Optional: still accept `drought_summary` for future use (e.g. displaying % severe) or remove if unused. For this plan we can leave the signature and just not use it for water cost.

Result: System Comparison shows base water cost only.

### 2.3 Pricing Estimation page

- **Input:** `comp` from `comparison_table_with_drought` (has base `effective_water`, WUE, state_abbr, pct_weeks_d2_plus).
- **Step:** Merge `pricing` (with `surge_pct`, `water_dollars_per_kgal`) into `comp` by `state_abbr`. Compute:
  - `effective_water_surge` = (WUE / L_PER_KGAL) × water_dollars_per_kgal × (1 + surge_pct × pct_weeks_d2_plus/100)
- **Use:** Use `effective_water_surge` for all water cost display and for `annual_water_usd` (water part). Keep electric as is.
- **Copy:** Add one line that effective water cost on this page includes drought surge and answers "what will water cost us today given known pricing and surcharges?"

Result: Only Pricing Estimation shows surge-adjusted water cost and annual water $.

---

## 3. Presentation / copy

### 3.1 Comparison Insights

- **"How calculations work" expander:**  
  - Effective water cost (here) = base rate only (no drought surge).  
  - Water stress = "How risky is this location's water future?" — forward-looking scarcity risk; unitless.  
  - One line: "For expected water cost including drought surcharges, see **Pricing Estimation**."
- **Table:** Optionally label water column "Eff. water (base ¢/kWh IT)" so it’s clear surge isn’t included.
- **Section or caption:** Add a single sentence that makes the split explicit: "**Water stress** = how risky is this location's water future? **Effective water cost** (base) = comparison at current base rates. For cost including drought surcharges, see Pricing Estimation."

### 3.2 Pricing Estimation

- **Caption or methodology:** State that effective water cost on this page includes **drought surge** and answers: "What will water cost us today given known pricing and drought surcharges?"
- Keep existing methodology expander; ensure it mentions surge in the water formula.

### 3.3 Optional: System Comparison

- Short caption that effective water cost here is at **base** rates (no surge); surge is on Pricing Estimation.

---

## 4. Summary

| Location | Effective water | Surge? | Framing |
|----------|-----------------|--------|---------|
| Comparison Insights (composite + table) | Base only | No | Water stress = future risk; water cost = base comparison; surge on Pricing Estimation. |
| System Comparison | Base only | No | Base rates. |
| Pricing Estimation | With surge | Yes | "What will water cost us today given pricing and surcharges?" |

This keeps composite focused on drought site risk (via water stress) and efficiency (electric + base water), and reserves surge for the cost-estimation page while making the two roles explicit in the app.
