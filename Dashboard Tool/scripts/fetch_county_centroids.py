#!/usr/bin/env python3
"""
Fetch US county centroids (lat/lon) from Census and save for the dashboard map.

Creates data/county_centroids.csv with columns: county_fips, latitude, longitude.
Required for the Home page map showing selected counties. Run once (or when you need to refresh).

Usage (from Counties+Zones Database):
  python "Dashboard Tool/scripts/fetch_county_centroids.py"
"""
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUT_PATH = DATA_DIR / "county_centroids.csv"
URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading from Census...")
    census = pd.read_csv(URL, dtype=str)
    census["county_fips"] = (
        census["STATEFP"].str.zfill(2) + census["COUNTYFP"].str.zfill(3)
    ).str[:5]
    census["latitude"] = pd.to_numeric(
        census["LATITUDE"].str.replace("+", "", regex=False), errors="coerce"
    )
    census["longitude"] = pd.to_numeric(
        census["LONGITUDE"].str.replace("+", "", regex=False), errors="coerce"
    )
    df = census[["county_fips", "latitude", "longitude"]].dropna(
        subset=["latitude", "longitude"]
    )
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
