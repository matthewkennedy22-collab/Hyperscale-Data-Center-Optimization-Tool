# Surge Price Integration Plan

## Goal

Integrate **drought surge pricing** into the app using the equation:

- **Power** (unchanged): `Power = (PUE × electric_cents_per_kwh) / 100`  → $/kWh IT  
- **Water** (new): `Water = (WUE / 3785.41) × (water_dollars_per_kgal + (Drought Surge Price) × (% Severe Drought))`  → $/kWh IT  
- **Effective utility cost** = Power + Water ($/kWh IT)

The surge file provides **per-state “Severe-drought price increase”** (e.g. 10%, 100%) as a percentage. Interpret as: the **effective water price** used in the formula is the base price plus a surge that scales with both the state’s surge % and the county’s % of time in severe drought:

- **Effective water $/kgal** = `water_dollars_per_kgal × (1 + surge_pct × pct_severe_drought / 100)`  
  where `surge_pct` is the state’s percentage as a decimal (e.g. 10% → 0.10), and `pct_severe_drought` is 0–100 (e.g. `pct_weeks_d2_plus`).

- **Effective water $/kWh IT** = `(WUE / L_PER_KGAL) × effective water $/kgal`  
  i.e. `(WUE / 3785.41) × water_dollars_per_kgal × (1 + surge_pct × pct_weeks_d2_plus / 100)`.

When surge data or drought data is missing, the formula falls back to the current behavior (no surge term).

---

## 1. Surge data file

**Source:** `surge_prices.xlsx - Sheet1.csv`  
- Columns: **State** (full name), **Severe-drought price increase** (e.g. "10%", "100%").

**Repo location:**  
- **Hyperscale repo:** `pricing/surge_prices_by_state.csv`  
- **AMPLYTICO Counties+Zones Database:** same path under that project’s root (e.g. `pricing/surge_prices_by_state.csv`).

**Format in repo:**  
- Normalize to: `state_abbr`, `surge_pct` (numeric 0–1, e.g. 10% → 0.10).  
- Add `state_abbr` by mapping **State** → `state_abbr` (e.g. via `pricing_by_state.csv` or a fixed mapping) so the app can join on `state_abbr` with pricing and rollup.

**Steps:**  
1. Copy or convert the source CSV into `pricing/surge_prices_by_state.csv` in both repos.  
2. Script or one-time step: read State + "Severe-drought price increase", parse % to decimal, add `state_abbr`, save.  
3. Optional: add `pricing/surge_prices_by_state.csv` to `.gitignore` only if it’s generated; if committed, do not ignore.

---

## 2. Data loading (`_utils.py`)

**New:**  
- Path: `PROJECT_ROOT / "pricing" / "surge_prices_by_state.csv"` (or same filename you use).  
- Loader: e.g. `_load_surge()` returning a DataFrame with at least `state_abbr`, `surge_pct`.  
- Cached with `@st.cache_data` like pricing.  
- If file missing or column missing: treat as “no surge” (surge_pct = 0 or no merge).

**Pricing merge:**  
- Option A (recommended): In a single “get pricing + surge” path, merge `pricing` with `surge` on `state_abbr`, so the object used everywhere has an optional `surge_pct` column (fill NaN with 0).  
- Option B: Keep `get_pricing()` as-is and add `get_surge()`; wherever effective water is computed, merge in surge (or look up by state) there.  

Recommendation: **Option A** — one “pricing” table that includes `surge_pct` when available, so all cost logic sees the same columns.

**Concrete:**  
- Add `_load_surge()` → DataFrame with `state_abbr`, `surge_pct`.  
- After loading pricing, if surge is available: `pricing = pricing.merge(surge[["state_abbr", "surge_pct"]], on="state_abbr", how="left")` and `pricing["surge_pct"] = pricing["surge_pct"].fillna(0)`.  
- Expose this via existing `get_pricing()` (so callers get pricing + surge in one place) or a new `get_pricing_with_surge()` that returns this merged table. Prefer reusing `get_pricing()` so no need to change every caller.

---

## 3. Effective water formula (single place)

**Current:**  
`effective_water = (WUE / L_PER_KGAL) * water_dollars_per_kgal` ($/kWh IT).

**New (when surge and drought are available):**  
`effective_water = (WUE / L_PER_KGAL) * water_dollars_per_kgal * (1 + surge_pct * pct_weeks_d2_plus / 100)`  
- `pct_weeks_d2_plus`: county’s % of weeks in severe drought (0–100), e.g. from drought summary.  
- `surge_pct`: state’s surge as decimal (0–1).  
- If no surge or no drought: use current formula (surge_pct=0 or pct_severe=0).

Apply this in:

1. **`comparison_table_with_drought()`**  
   - Already has `pricing`, `drought_summary`, and builds `effective_water_AE`, `effective_water_WEC`.  
   - Merge pricing (with `surge_pct`) and use `pct_weeks_d2_plus` from drought summary.  
   - Replace the two lines that set `effective_water_AE` and `effective_water_WEC` with the new formula (with fallback when `surge_pct` or `pct_weeks_d2_plus` is missing).

2. **`selected_counties_df()`**  
   - Currently only gets rollup + pricing and computes effective water without drought.  
   - For consistency with the rest of the app, optionally add parameters: `drought_summary=None`, and use the same “pricing” object that may include `surge_pct`.  
   - If `drought_summary` is provided: merge county → `pct_weeks_d2_plus`, then use the new water formula.  
   - If `drought_summary` is None: keep current formula (or use 0 for pct_severe so surge term is 0).  
   - This way System Comparison can show water cost with surge when drought data is available, without changing its UI contract (still `selected_counties_df(rollup, pricing)` from the page; internally we can call it with optional drought_summary if the page has it).

---

## 4. Where effective water is used (no formula change, just ensure they use the updated comp/pricing)

- **Comparison Insights (page 4)**  
  - Uses `comp` from `comparison_table_with_drought()`.  
  - Once that function uses the new formula, `comp["effective_water"]` and composite scoring will automatically include surge.  
  - Update the “How calculations work” expander to mention that effective water cost can include a state-level drought surge scaled by % time in severe drought.

- **Pricing Estimation (page 5)**  
  - Uses the same `comp` from `comparison_table_with_drought()`.  
  - Annual water (and total) cost will automatically include surge.  
  - Add a short note or expander that water cost may include a drought surge component when surge and drought data are present.

- **System Comparison (page 3)**  
  - Uses `selected_counties_df(rollup, pricing)`.  
  - To show surge here too: have the page pass `drought_summary` (and ensure `pricing` includes `surge_pct`). Then extend `selected_counties_df(rollup, pricing, drought_summary=None)` and use the new formula when `drought_summary` is not None.  
  - If you prefer to keep System Comparison “base only,” you can leave `selected_counties_df` as-is and only add surge in `comparison_table_with_drought` and thus in Insights + Pricing; the plan stays valid, only System Comparison would not show surge.

---

## 5. Composite scoring (Comparison Insights)

- Composite already uses `effective_electric_n`, `effective_water_n`, `water_stress_n`.  
- `effective_water` (and hence `effective_water_n`) will come from `comparison_table_with_drought()`.  
- Once that function uses the new water formula, **no separate change** is needed for composite scoring; it will automatically reflect surge in the water-cost term.  
- Only update the copy in the expander so users understand that “effective water cost” can include the drought surge.

---

## 6. File and repo checklist

- [ ] Add `pricing/surge_prices_by_state.csv` to **Hyperscale repo** (and optionally to AMPLYTICO Counties+Zones Database) with columns `state_abbr`, `surge_pct`.  
- [ ] Implement conversion script or one-time conversion from `surge_prices.xlsx - Sheet1.csv` (State + "Severe-drought price increase") to that format.  
- [ ] In `_utils.py`: add surge path and loader; merge surge into pricing (or return merged table from `get_pricing()`).  
- [ ] In `_utils.py`: update `comparison_table_with_drought()` to use new effective water formula when `surge_pct` and `pct_weeks_d2_plus` exist.  
- [ ] In `_utils.py`: optionally update `selected_counties_df()` to accept `drought_summary` and use the new formula so System Comparison can show surge when drought data exists.  
- [ ] In **Comparison Insights**: update “How calculations work” text to describe drought surge in water cost.  
- [ ] In **Pricing Estimation**: add a short note that water cost may include a drought surge.  
- [ ] Test with and without surge file; with and without drought data; confirm composite and pricing numbers and UI text.

---

## 7. Summary

| Area                    | Change |
|-------------------------|--------|
| Repo / AMPLYTICO        | Add `pricing/surge_prices_by_state.csv` (state_abbr, surge_pct). |
| _utils: load            | Load surge; merge into pricing (surge_pct, fill NaN with 0). |
| _utils: comparison_table_with_drought | Effective water = (WUE/L_PER_KGAL)*water_dollars_per_kgal*(1 + surge_pct*pct_weeks_d2_plus/100). |
| _utils: selected_counties_df | Optional drought_summary; same formula when present. |
| Comparison Insights     | Use updated comp (no code change); update expander text. |
| Pricing Estimation      | Use updated comp (no code change); add note on surge. |
| Composite scoring       | No code change; uses updated effective_water from comp. |

This keeps a single definition of “effective water” (with optional surge) and wires it through existing comparison and pricing flows so both **pricing estimations** and **composite scoring** use the new surge-based water cost.
