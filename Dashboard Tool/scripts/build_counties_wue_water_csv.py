#!/usr/bin/env python3
"""
Build a CSV of all counties with FIPS, state abbr, state name, average WUE (AE and WEC),
state water price, and effective water cost in ¢/kWh IT (WUE L/kWh × $/kgal → ¢/kWh IT).

Uses: data/county_week_rollup.csv (or county_month_rollup.csv) and pricing/pricing_by_state.csv.
Output: data/counties_wue_water.csv

Usage (run from Counties+Zones Database or Dashboard Tool):
  python "Dashboard Tool/scripts/build_counties_wue_water_csv.py"
  python "Dashboard Tool/scripts/build_counties_wue_water_csv.py" --output data/counties_wue_water.csv
"""

import argparse
from pathlib import Path

import pandas as pd

# Same conversion as dashboard: WUE in L/kWh, pricing in $/kgal. 1 kgal = 3785.411784 L.
L_PER_KGAL = 3785.411784

SCRIPT_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = DASHBOARD_DIR.parent
# Rollup may live in project root data/ or Dashboard Tool/data/
DATA_DIRS = [PROJECT_ROOT / "data", DASHBOARD_DIR / "data"]
ROLLUP_WEEK = DATA_DIRS[0] / "county_week_rollup.csv"
ROLLUP_MONTH = DATA_DIRS[0] / "county_month_rollup.csv"
PRICING_PATH = PROJECT_ROOT / "pricing" / "pricing_by_state.csv"
DEFAULT_OUTPUT = DATA_DIRS[0] / "counties_wue_water.csv"


def main() -> None:
    p = argparse.ArgumentParser(description="Build counties CSV with WUE and effective water cost")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    p.add_argument("--rollup", "-r", type=Path, default=None, help="Rollup CSV (default: data/county_week_rollup.csv or county_month)")
    args = p.parse_args()

    rollup_path = args.rollup
    if rollup_path is None:
        for d in DATA_DIRS:
            w, m = d / "county_week_rollup.csv", d / "county_month_rollup.csv"
            if w.is_file():
                rollup_path = w
                break
            if m.is_file():
                rollup_path = m
                break
    if rollup_path is None or not rollup_path.is_file():
        raise FileNotFoundError(f"Rollup not found. Run build_county_week_rollup.py first or set --rollup. Looked in {DATA_DIRS}")
    if not PRICING_PATH.is_file():
        raise FileNotFoundError(f"Pricing file not found: {PRICING_PATH}")

    print(f"Reading rollup: {rollup_path}")
    rollup = pd.read_csv(rollup_path, low_memory=False)
    if "county_fips" in rollup.columns:
        rollup["county_fips"] = rollup["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)

    # One row per county: mean WUE across all weeks/years
    group_cols = [c for c in ["county_fips", "county_name", "state_abbr", "state_full"] if c in rollup.columns]
    if "state_full" not in group_cols:
        group_cols = [c for c in ["county_fips", "county_name", "state_abbr"] if c in rollup.columns]
    agg = {}
    if "AE_WUE" in rollup.columns:
        agg["AE_WUE_avg"] = ("AE_WUE", "mean")
    if "WEC_WUE" in rollup.columns:
        agg["WEC_WUE_avg"] = ("WEC_WUE", "mean")
    if not agg or not group_cols:
        raise RuntimeError("Rollup must contain county_fips, county_name, state_abbr and at least one of AE_WUE, WEC_WUE")

    counties = rollup.groupby(group_cols, dropna=False).agg(**agg).reset_index()

    print(f"Loading pricing: {PRICING_PATH}")
    pricing = pd.read_csv(PRICING_PATH)
    pricing = pricing.rename(columns={"state_full": "state_name"})[["state_abbr", "state_name", "water_dollars_per_kgal"]].drop_duplicates("state_abbr")
    counties = counties.merge(pricing, on="state_abbr", how="left")
    if "state_name" not in counties.columns:
        counties["state_name"] = counties["state_abbr"]
    else:
        counties["state_name"] = counties["state_name"].fillna(counties["state_abbr"])
    if "state_full" in counties.columns:
        counties = counties.drop(columns=["state_full"])

    # Round WUE first so effective_water recomputes exactly from printed values
    if "AE_WUE_avg" in counties.columns:
        counties["AE_WUE_avg"] = counties["AE_WUE_avg"].round(6)
    if "WEC_WUE_avg" in counties.columns:
        counties["WEC_WUE_avg"] = counties["WEC_WUE_avg"].round(6)
    if "water_dollars_per_kgal" in counties.columns:
        counties["water_dollars_per_kgal"] = counties["water_dollars_per_kgal"].round(6)

    # Effective water: (WUE L/kWh / L_PER_KGAL) * $/kgal = $/kWh IT; output in ¢/kWh IT (× 100) for readability
    if "AE_WUE_avg" in counties.columns and "water_dollars_per_kgal" in counties.columns:
        counties["effective_water_AE"] = ((counties["AE_WUE_avg"] / L_PER_KGAL) * counties["water_dollars_per_kgal"] * 100).round(3)
    if "WEC_WUE_avg" in counties.columns and "water_dollars_per_kgal" in counties.columns:
        counties["effective_water_WEC"] = ((counties["WEC_WUE_avg"] / L_PER_KGAL) * counties["water_dollars_per_kgal"] * 100).round(3)

    # Output columns in requested order
    out_cols = ["county_name", "county_fips", "state_abbr", "state_name"]
    if "AE_WUE_avg" in counties.columns:
        out_cols.append("AE_WUE_avg")
    if "WEC_WUE_avg" in counties.columns:
        out_cols.append("WEC_WUE_avg")
    out_cols.append("water_dollars_per_kgal")
    if "effective_water_AE" in counties.columns:
        out_cols.append("effective_water_AE")
    if "effective_water_WEC" in counties.columns:
        out_cols.append("effective_water_WEC")

    out_df = counties[[c for c in out_cols if c in counties.columns]].copy()
    out_df = out_df.round(6)
    # Ensure county_fips is always 5 digits with leading zeros (e.g. 01001)
    if "county_fips" in out_df.columns:
        out_df["county_fips"] = out_df["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    # Column headers with units for clarity
    header_units = {
        "AE_WUE_avg": "AE_WUE_avg (L/kWh)",
        "WEC_WUE_avg": "WEC_WUE_avg (L/kWh)",
        "water_dollars_per_kgal": "water_dollars_per_kgal ($/kgal)",
        "effective_water_AE": "effective_water_AE (¢/kWh IT)",
        "effective_water_WEC": "effective_water_WEC (¢/kWh IT)",
    }
    out_df = out_df.rename(columns={k: v for k, v in header_units.items() if k in out_df.columns})
    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote {len(out_df)} rows to {out_path}")
    print(f"  Columns: {list(out_df.columns)}")


if __name__ == "__main__":
    main()
