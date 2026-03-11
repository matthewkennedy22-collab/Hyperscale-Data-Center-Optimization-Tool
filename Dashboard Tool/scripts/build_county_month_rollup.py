#!/usr/bin/env python3
"""
Phase 1 — Data prep: build county × month rollup from weather+PUE/WUE data.

Reads the (large) hourly weather + PUE/WUE CSV, aggregates to one row per
county per month with mean temp, RH, pressure, AE_PUE, AE_WUE, WEC_PUE, WEC_WUE.
Writes to the parent project's data folder (Counties+Zones Database/data/).

Usage (run from Counties+Zones Database or from Dashboard Tool):
  python "Dashboard Tool/scripts/build_county_month_rollup.py"
  python "Dashboard Tool/scripts/build_county_month_rollup.py" --input /path/to/big.csv --output data/county_month_rollup.csv
"""

import argparse
from pathlib import Path

import pandas as pd

# Dashboard Tool/scripts/ -> Dashboard Tool -> Counties+Zones Database
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Prefer the full 3.9 GB CSV (all counties); fallback to smaller files
PARENT_FOLDER = PROJECT_ROOT.parent  # AMPLYTICO
DEFAULT_INPUTS = [
    PARENT_FOLDER / "FINAL_counties_with_pue_wue.csv",  # ~4 GB, all counties
    PROJECT_ROOT / "weather_hourly_with_counties_with_pue_wue.csv",
    PROJECT_ROOT / "PUE WUE SIM" / "weather_hourly_with_counties_with_pue_wue.csv",
]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "county_month_rollup.csv"


def find_weather_file(input_path: Path | None) -> Path:
    if input_path and input_path.is_file():
        return input_path
    for p in DEFAULT_INPUTS:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "No weather+PUE/WUE CSV found. Set --input or place file at "
        f"one of {[str(p) for p in DEFAULT_INPUTS]}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Build county × month rollup for dashboard")
    p.add_argument("--input", "-i", type=Path, default=None, help="Hourly weather+PUE/WUE CSV")
    p.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output rollup CSV")
    p.add_argument("--chunk", type=int, default=500_000, help="Chunk size for reading (default 500k)")
    args = p.parse_args()

    inp = find_weather_file(args.input)
    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading {inp} in chunks...")
    chunks = []
    for i, chunk in enumerate(pd.read_csv(inp, chunksize=args.chunk, low_memory=False)):
        if "timestamp" in chunk.columns:
            ts = pd.to_datetime(chunk["timestamp"], errors="coerce", utc=True)
            try:
                chunk["month"] = ts.dt.month
            except AttributeError:
                chunk["month"] = ts.apply(lambda x: x.month if pd.notna(x) and hasattr(x, "month") else 1)
        else:
            chunk["month"] = 1
        if "year" not in chunk.columns:
            chunk["year"] = 2024
        chunk["year"] = chunk["year"].fillna(2024).astype(int)
        agg_cols = [c for c in ["temp_c", "rh_pct", "pressure_hpa", "AE_PUE", "AE_WUE", "WEC_PUE", "WEC_WUE"] if c in chunk.columns]
        group_cols = [c for c in ["county_fips", "county_name", "state_abbr", "state_full", "year", "month"] if c in chunk.columns]
        if not group_cols or not agg_cols:
            chunks.append(chunk)
            continue
        rolled = chunk.groupby(group_cols, dropna=False)[agg_cols].mean().reset_index()
        chunks.append(rolled)
        if (i + 1) % 10 == 0:
            print(f"  Chunk {i+1}...")

    if not chunks:
        raise RuntimeError("No data read from CSV")

    df = pd.concat(chunks, ignore_index=True)
    group_cols = [c for c in ["county_fips", "county_name", "state_abbr", "state_full", "year", "month"] if c in df.columns]
    agg_cols = [c for c in ["temp_c", "rh_pct", "pressure_hpa", "AE_PUE", "AE_WUE", "WEC_PUE", "WEC_WUE"] if c in df.columns]
    df = df.groupby(group_cols, dropna=False)[agg_cols].mean().reset_index()

    if "county_fips" in df.columns:
        df["county_fips"] = df["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)

    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
    print(f"  Counties: {df['county_fips'].nunique()}, Months: {df['month'].nunique()}")

    counties = df[["county_fips", "county_name", "state_abbr"]].drop_duplicates().sort_values(["state_abbr", "county_name"])
    counties_path = out.parent / "counties.csv"
    counties.to_csv(counties_path, index=False)
    print(f"Wrote {len(counties)} counties to {counties_path}")


if __name__ == "__main__":
    main()
