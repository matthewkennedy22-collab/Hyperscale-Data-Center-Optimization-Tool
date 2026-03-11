"""Shared data loading and helpers for the county comparison dashboard."""
from pathlib import Path

import pandas as pd
import streamlit as st

from ui import PLOTLY_COLORWAY

# WUE in Lei & Masanet is typically reported as liters per kWh (L/kWh).
# Pricing file uses $ per thousand gallons (kgal). 1 kgal = 3785.411784 liters.
L_PER_KGAL = 3785.411784

# Parent of Dashboard Tool = main project (Counties+Zones Database)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
# Prefer weekly rollup; fall back to monthly for backward compatibility
ROLLUP_WEEK_PATH = DATA_DIR / "county_week_rollup.csv"
ROLLUP_MONTH_PATH = DATA_DIR / "county_month_rollup.csv"
ROLLUP_PATH = ROLLUP_WEEK_PATH  # primary; loader falls back to month if week missing
COUNTIES_PATH = DATA_DIR / "counties.csv"
CENTROIDS_PATH = DATA_DIR / "county_centroids.csv"
PRICING_PATH = PROJECT_ROOT / "pricing" / "pricing_by_state.csv"
DROUGHT_PATH = PROJECT_ROOT / "drought_weekly_by_county_2015_2024_week52only.csv"
CENSUS_CENTROIDS_URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"


@st.cache_data
def _load_rollup():
    path = ROLLUP_WEEK_PATH if ROLLUP_WEEK_PATH.is_file() else ROLLUP_MONTH_PATH
    if not path.is_file():
        return None
    df = pd.read_csv(path)
    if "county_fips" in df.columns:
        df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    return df


@st.cache_data
def _load_pricing():
    if not PRICING_PATH.is_file():
        return None
    return pd.read_csv(PRICING_PATH)


@st.cache_data
def _load_counties():
    if COUNTIES_PATH.is_file():
        df = pd.read_csv(COUNTIES_PATH)
        if "county_fips" in df.columns:
            df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
        return df
    rollup = _load_rollup()
    if rollup is None:
        return None
    return rollup[["county_fips", "county_name", "state_abbr"]].drop_duplicates().sort_values(["state_abbr", "county_name"])


def get_rollup():
    return _load_rollup()


def get_pricing():
    return _load_pricing()


def get_counties():
    return _load_counties()


@st.cache_data
def _load_county_centroids():
    """Load county_fips -> latitude, longitude. Build from Census if file missing."""
    if CENTROIDS_PATH.is_file():
        df = pd.read_csv(CENTROIDS_PATH)
        if "county_fips" in df.columns:
            df["county_fips"] = df["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        return df
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        census = pd.read_csv(CENSUS_CENTROIDS_URL, dtype=str, timeout=30)
        if "STATEFP" not in census.columns or "COUNTYFP" not in census.columns:
            return None
        census["county_fips"] = (census["STATEFP"].str.zfill(2) + census["COUNTYFP"].str.zfill(3)).str[:5]
        census["latitude"] = pd.to_numeric(census["LATITUDE"].str.replace("+", "", regex=False), errors="coerce")
        census["longitude"] = pd.to_numeric(census["LONGITUDE"].str.replace("+", "", regex=False), errors="coerce")
        df = census[["county_fips", "latitude", "longitude"]].dropna(subset=["latitude", "longitude"])
        df.to_csv(CENTROIDS_PATH, index=False)
        return df
    except Exception:
        return None


def get_county_centroids():
    return _load_county_centroids()


def ensure_data():
    """Show warning if required data files are missing."""
    missing = []
    if not ROLLUP_WEEK_PATH.is_file() and not ROLLUP_MONTH_PATH.is_file():
        missing.append("data/county_week_rollup.csv (run scripts/build_county_week_rollup.py)")
    if not PRICING_PATH.is_file():
        missing.append(str(PRICING_PATH))
    if missing:
        st.error("Missing data files. Run data prep first:\n- " + "\n- ".join(missing))
        st.stop()


def render_sidebar():
    """Render county selector in sidebar and set session_state['selected_county_fips'] and selected_county_labels.
    Uses a form so 'Add' does not close the dropdown on every click; selected list is shown with remove options."""
    counties_df = get_counties()
    with st.sidebar:
        st.header("Counties")
        if counties_df is None or counties_df.empty:
            st.warning("No county list. Run: python scripts/build_county_week_rollup.py ...")
            st.session_state["selected_county_fips"] = []
            st.session_state["selected_county_labels"] = []
            return
        counties_df = counties_df.copy()
        counties_df["_label"] = counties_df["county_name"] + ", " + counties_df["state_abbr"]
        options = counties_df.set_index("county_fips")["_label"].to_dict()
        all_labels = list(options.values())
        fips_by_label = {v: k for k, v in options.items()}
        selected_fips = st.session_state.get("selected_county_fips", [])
        selected_labels = st.session_state.get("selected_county_labels", [])
        # Keep in sync: if we have fips but no labels, rebuild labels from fips
        if selected_fips and not selected_labels:
            selected_labels = [options.get(str(f).zfill(5)) for f in selected_fips if options.get(str(f).zfill(5))]
            st.session_state["selected_county_labels"] = selected_labels
        if selected_labels and not selected_fips:
            selected_fips = [fips_by_label.get(l) for l in selected_labels if fips_by_label.get(l)]
            st.session_state["selected_county_fips"] = selected_fips
        available_labels = [l for l in all_labels if l not in selected_labels]
        with st.form("add_county_form", clear_on_submit=True):
            add_choices = st.multiselect(
                "Add counties",
                options=available_labels,
                default=[],
                placeholder="Search or choose...",
                key="add_county_multiselect",
            )
            add_clicked = st.form_submit_button("Add to selection")
        if add_clicked and add_choices:
            new_labels = list(selected_labels) + [c for c in add_choices if c not in selected_labels]
            new_fips = [fips_by_label[l] for l in new_labels if l in fips_by_label]
            st.session_state["selected_county_labels"] = new_labels
            st.session_state["selected_county_fips"] = new_fips
            st.rerun()
        if selected_labels:
            with st.expander(f"Selected ({len(selected_labels)})", expanded=True):
                for i, label in enumerate(selected_labels):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.caption(label)
                    with c2:
                        if st.button("✕", key=f"remove_county_{i}", help="Remove this county"):
                            new_labels = [l for j, l in enumerate(selected_labels) if j != i]
                            new_fips = [fips_by_label[l] for l in new_labels if l in fips_by_label]
                            st.session_state["selected_county_labels"] = new_labels
                            st.session_state["selected_county_fips"] = new_fips
                            st.rerun()
                if st.button("Clear selection", use_container_width=True, key="clear_all_sidebar"):
                    st.session_state["selected_county_fips"] = []
                    st.session_state["selected_county_labels"] = []
                    st.rerun()
        else:
            st.caption("No counties selected. Add one above.")
        st.divider()
        has_rollup = ROLLUP_WEEK_PATH.is_file() or ROLLUP_MONTH_PATH.is_file()
        has_pricing = PRICING_PATH.is_file()
        has_drought = DROUGHT_PATH.is_file()
        status = "Rollup ✓  Pricing ✓  Drought ✓" if (has_rollup and has_pricing and has_drought) else f"Rollup {'✓' if has_rollup else '✗'}  Pricing {'✓' if has_pricing else '✗'}  Drought {'✓' if has_drought else '✗'}"
        with st.expander("Data status", expanded=False):
            st.caption(status)


def lighten_hex(hex_color, factor=0.88):
    """Return a lightened hex color for table backgrounds (factor = fraction of original; 0.88 = light fill)."""
    hex_color = (hex_color or "#cccccc").lstrip("#")
    if len(hex_color) != 6:
        return "#f5f5f5"
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(255 * (1 - factor) + r * factor))
    g = min(255, int(255 * (1 - factor) + g * factor))
    b = min(255, int(255 * (1 - factor) + b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_county_color_map():
    """Return (ordered_county_labels, color_map) so the same county has the same color on every page.
    Order is the selection order from the sidebar; colors from PLOTLY_COLORWAY."""
    labels = st.session_state.get("selected_county_labels", [])
    if not labels:
        # Fallback: build from selected FIPS so colors stay consistent after refresh
        fips_list = st.session_state.get("selected_county_fips", [])
        if not fips_list:
            return [], {}
        counties_df = get_counties()
        if counties_df is None or counties_df.empty:
            return [], {}
        counties_df = counties_df[counties_df["county_fips"].astype(str).str.zfill(5).isin([str(f).zfill(5) for f in fips_list])].drop_duplicates("county_fips")
        counties_df = counties_df.copy()
        counties_df["county_fips"] = counties_df["county_fips"].astype(str).str.zfill(5)
        counties_df["_label"] = counties_df["county_name"] + ", " + counties_df["state_abbr"].astype(str)
        fips_to_label = counties_df.set_index("county_fips")["_label"].to_dict()
        labels = [fips_to_label.get(str(f).zfill(5), str(f)) for f in fips_list]
    color_map = {label: PLOTLY_COLORWAY[i % len(PLOTLY_COLORWAY)] for i, label in enumerate(labels)}
    return labels, color_map


def sort_df_by_county_order(df, county_col="County"):
    """Sort dataframe so rows follow sidebar selection order (for consistent legend/color order)."""
    ordered_labels, _ = get_county_color_map()
    if not ordered_labels or county_col not in df.columns:
        return df
    order_key = {lbl: i for i, lbl in enumerate(ordered_labels)}
    df = df.copy()
    df["_color_order"] = df[county_col].map(order_key)
    df["_color_order"] = df["_color_order"].fillna(999).astype(int)
    df = df.sort_values("_color_order").drop(columns=["_color_order"])
    return df


def _load_drought_impl(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    df = pd.read_csv(path)
    if "county_fips" in df.columns:
        df["county_fips"] = df["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    if "week_end_date" in df.columns:
        df["week_end_date"] = pd.to_datetime(df["week_end_date"], errors="coerce")
        if "year" not in df.columns:
            df["year"] = df["week_end_date"].dt.year
        if "week_number" not in df.columns:
            iso = df["week_end_date"].dt.isocalendar()
            df["week_number"] = iso.week.fillna(1).astype(int)
    return df


@st.cache_data(ttl=3600)
def _load_drought(_cache_key: int = 0):
    """Load drought CSV. _cache_key should be file mtime so cache invalidates when file is updated."""
    return _load_drought_impl(DROUGHT_PATH)


def get_drought():
    """Load drought data; use file mtime so updated files (e.g. with new CT data) are re-read."""
    cache_key = int(DROUGHT_PATH.stat().st_mtime) if DROUGHT_PATH.is_file() else 0
    return _load_drought(cache_key)


def selected_counties_df(rollup, pricing):
    """Filter rollup by session-state selected county FIPS and join pricing."""
    if rollup is None or rollup.empty:
        return None
    selected = st.session_state.get("selected_county_fips", [])
    if not selected:
        return None
    rollup_fips = rollup["county_fips"].astype(str).str.zfill(5)
    mask = rollup_fips.isin([str(f).zfill(5) for f in selected])
    df = rollup[mask].copy()
    if df.empty:
        return df
    if pricing is not None and not pricing.empty and "state_abbr" in df.columns:
        df = df.merge(
            pricing[["state_abbr", "electric_cents_per_kwh", "water_dollars_per_kgal"]],
            on="state_abbr",
            how="left",
        )
        df["effective_electric_AE"] = df["AE_PUE"] * df["electric_cents_per_kwh"]
        df["effective_electric_WEC"] = df["WEC_PUE"] * df["electric_cents_per_kwh"]
        # Convert WUE from L/kWh to kgal/kWh to match $/kgal pricing
        df["effective_water_AE"] = (df["AE_WUE"] / L_PER_KGAL) * df["water_dollars_per_kgal"]
        df["effective_water_WEC"] = (df["WEC_WUE"] / L_PER_KGAL) * df["water_dollars_per_kgal"]
    return df


def selected_drought_df(drought):
    """Filter drought by session-state selected county FIPS."""
    if drought is None or drought.empty:
        return None
    selected = st.session_state.get("selected_county_fips", [])
    if not selected:
        return None
    fips_norm = [str(f).zfill(5) for f in selected]
    mask = drought["county_fips"].astype(str).str.zfill(5).isin(fips_norm)
    return drought[mask].copy()


def get_drought_summary_by_county(drought):
    """Return one row per county: county_fips, mean_drought, max_drought, pct_weeks_d1_plus, pct_weeks_d2_plus (severe: index 2–4)."""
    if drought is None or drought.empty or "drought_level_avg" not in drought.columns:
        return None
    df = drought.copy()
    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    summary = df.groupby("county_fips", as_index=False).agg(
        mean_drought=("drought_level_avg", "mean"),
        max_drought=("drought_level_avg", "max"),
        pct_weeks_d1_plus=("drought_level_avg", lambda s: (s >= 1).mean() * 100),
        pct_weeks_d2_plus=("drought_level_avg", lambda s: (s >= 2).mean() * 100),  # severe (D2–D4)
    ).round(4)
    return summary


def get_drought_by_year(drought, counties_df):
    """
    Return drought aggregated by county and year for selected counties.
    Columns: county_fips, County, year, mean_drought, pct_d1_plus.
    """
    if drought is None or drought.empty or "drought_level_avg" not in drought.columns:
        return None
    df = selected_drought_df(drought)
    if df is None or df.empty:
        return None
    if "year" not in df.columns and "week_end_date" in df.columns:
        df = df.copy()
        df["year"] = pd.to_datetime(df["week_end_date"], errors="coerce").dt.year
    if "year" not in df.columns:
        return None
    by_year = df.groupby(["county_fips", "year"], as_index=False).agg(
        mean_drought=("drought_level_avg", "mean"),
        pct_d1_plus=("drought_level_avg", lambda s: (s >= 1).mean() * 100),
    ).round(4)
    if counties_df is not None and not counties_df.empty:
        counties_df = counties_df[["county_fips", "county_name", "state_abbr"]].drop_duplicates("county_fips")
        by_year = by_year.merge(counties_df, on="county_fips", how="left")
        by_year["County"] = by_year["county_name"].fillna("") + ", " + by_year["state_abbr"].fillna("")
    else:
        by_year["County"] = by_year["county_fips"]
    return by_year


def comparison_table_with_drought(rollup, pricing, drought_summary):
    """
    Build county × system (AE/WEC) table with PUE, WUE, costs, drought, and water stress.
    Returns long-format DataFrame: county_fips, county_name, state_abbr, system, PUE, WUE,
    effective_electric, effective_water, mean_drought, pct_weeks_d2_plus, water_stress (WUE × (1 + pct time in severe drought)).
    Severe drought = U.S. Drought Monitor index 2–4 (D2–D4); pct as decimal 0–1.
    """
    if rollup is None or rollup.empty:
        return None
    selected = st.session_state.get("selected_county_fips", [])
    if not selected:
        return None
    fips_norm = [str(f).zfill(5) for f in selected]
    rollup = rollup.copy()
    rollup["county_fips"] = rollup["county_fips"].astype(str).str.zfill(5)
    df = rollup[rollup["county_fips"].isin(fips_norm)]
    if df.empty:
        return None
    annual = df.groupby(["county_fips", "county_name", "state_abbr"], as_index=False).agg(
        AE_PUE=("AE_PUE", "mean"),
        AE_WUE=("AE_WUE", "mean"),
        WEC_PUE=("WEC_PUE", "mean"),
        WEC_WUE=("WEC_WUE", "mean"),
    )
    if pricing is not None and not pricing.empty:
        annual = annual.merge(
            pricing[["state_abbr", "electric_cents_per_kwh", "water_dollars_per_kgal"]],
            on="state_abbr",
            how="left",
        )
        annual["effective_electric_AE"] = annual["AE_PUE"] * annual["electric_cents_per_kwh"]
        annual["effective_electric_WEC"] = annual["WEC_PUE"] * annual["electric_cents_per_kwh"]
        # Convert WUE from L/kWh to kgal/kWh to match $/kgal pricing
        annual["effective_water_AE"] = (annual["AE_WUE"] / L_PER_KGAL) * annual["water_dollars_per_kgal"]
        annual["effective_water_WEC"] = (annual["WEC_WUE"] / L_PER_KGAL) * annual["water_dollars_per_kgal"]
    else:
        annual["effective_electric_AE"] = annual["effective_electric_WEC"] = 0.0
        annual["effective_water_AE"] = annual["effective_water_WEC"] = 0.0
    if drought_summary is not None and not drought_summary.empty:
        annual = annual.merge(drought_summary, on="county_fips", how="left")
        annual["mean_drought"] = annual["mean_drought"].fillna(0)
    else:
        annual["mean_drought"] = 0.0
        annual["max_drought"] = 0.0
        annual["pct_weeks_d1_plus"] = 0.0
        annual["pct_weeks_d2_plus"] = 0.0
    if "pct_weeks_d2_plus" not in annual.columns:
        annual["pct_weeks_d2_plus"] = 0.0
    # Long format: one row per county per system; water_stress = WUE × (1 + pct_weeks_d2_plus/100)
    rows = []
    for _, r in annual.iterrows():
        for system, pue_col, wue_col, elec_col, water_col in [
            ("AE", "AE_PUE", "AE_WUE", "effective_electric_AE", "effective_water_AE"),
            ("WEC", "WEC_PUE", "WEC_WUE", "effective_electric_WEC", "effective_water_WEC"),
        ]:
            mean_d = r.get("mean_drought", 0) or 0
            pct_severe = r.get("pct_weeks_d2_plus", 0) or 0  # % of weeks in severe drought (index 2–4)
            wue = r[wue_col]
            # Water stress: WUE × (1 + time in severe drought as decimal)
            water_stress = float(wue) * (1 + pct_severe / 100) if pd.notna(wue) else None
            rows.append({
                "county_fips": r["county_fips"],
                "county_name": r["county_name"],
                "state_abbr": r["state_abbr"],
                "County": f"{r['county_name']}, {r['state_abbr']}",
                "system": system,
                "PUE": r[pue_col],
                "WUE": r[wue_col],
                "effective_electric": r[elec_col],
                "effective_water": r[water_col],
                "mean_drought": mean_d,
                "pct_weeks_d1_plus": r.get("pct_weeks_d1_plus", 0),
                "pct_weeks_d2_plus": r.get("pct_weeks_d2_plus", 0),
                "water_stress": water_stress,
            })
    return pd.DataFrame(rows)
