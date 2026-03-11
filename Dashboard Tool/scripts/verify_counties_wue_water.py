#!/usr/bin/env python3
"""
Verify data/counties_wue_water.csv against the rollup and pricing sources.
Optionally compare county FIPS/state with DuckDB if available.

Usage:
  python "Dashboard Tool/scripts/verify_counties_wue_water.py"
  python "Dashboard Tool/scripts/verify_counties_wue_water.py" --csv data/counties_wue_water.csv --db ~/Downloads/amplytico.duckdb
"""

import argparse
from pathlib import Path

import pandas as pd

L_PER_KGAL = 3785.411784
SCRIPT_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = DASHBOARD_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
PRICING_PATH = PROJECT_ROOT / "pricing" / "pricing_by_state.csv"


def main() -> None:
    p = argparse.ArgumentParser(description="Verify counties_wue_water.csv against rollup and pricing")
    p.add_argument("--csv", type=Path, default=DATA_DIR / "counties_wue_water.csv", help="Counties WUE/water CSV")
    p.add_argument("--rollup", type=Path, default=None, help="Rollup CSV (default: data/county_week_rollup.csv)")
    p.add_argument("--db", type=Path, default=None, help="DuckDB path for optional DB cross-check")
    args = p.parse_args()

    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"ERROR: CSV not found: {csv_path}")
        return

    rollup_path = args.rollup
    if rollup_path is None:
        rollup_path = DATA_DIR / "county_week_rollup.csv"
        if not rollup_path.is_file():
            rollup_path = DATA_DIR / "county_month_rollup.csv"
    if not rollup_path.is_file():
        print(f"WARN: Rollup not found at {rollup_path}; skipping rollup checks.")

    print("Loading counties_wue_water.csv ...")
    out = pd.read_csv(csv_path)
    # Normalize column names: strip " (units)" so we can use standard names (CSV may have headers with units)
    out.columns = [c.split(" (")[0] if " (" in c else c for c in out.columns]
    out["county_fips"] = out["county_fips"].astype(str).str.lstrip("'").str.replace(r"\.0$", "", regex=True).str.zfill(5)
    issues = []

    # 1) Pricing: water_dollars_per_kgal and state_name match pricing file
    if PRICING_PATH.is_file():
        pricing = pd.read_csv(PRICING_PATH)
        pricing = pricing.rename(columns={"state_full": "state_name"})[["state_abbr", "state_name", "water_dollars_per_kgal"]].drop_duplicates("state_abbr")
        for _, row in out.iterrows():
            sa = row["state_abbr"]
            prow = pricing[pricing["state_abbr"] == sa]
            if prow.empty:
                issues.append(f"State abbr '{sa}' (county {row['county_fips']}) not in pricing file.")
            else:
                prow = prow.iloc[0]
                if abs(row["water_dollars_per_kgal"] - prow["water_dollars_per_kgal"]) > 1e-6:
                    issues.append(f"water_dollars_per_kgal mismatch {row['county_fips']} {row['state_abbr']}: CSV={row['water_dollars_per_kgal']} pricing={prow['water_dollars_per_kgal']}")
                if str(row["state_name"]) != str(prow["state_name"]):
                    issues.append(f"state_name mismatch {row['county_fips']}: CSV='{row['state_name']}' pricing='{prow['state_name']}'")
        print("  Pricing: state_abbr, state_name, water_dollars_per_kgal checked against pricing file.")
    else:
        print("  WARN: pricing file not found; skipping pricing checks.")

    # 2) Effective water formula: CSV stores ¢/kWh IT = (WUE_avg / L_PER_KGAL) * water_dollars_per_kgal * 100
    out["_eff_ae_cents"] = ((out["AE_WUE_avg"] / L_PER_KGAL) * out["water_dollars_per_kgal"] * 100).round(3)
    out["_eff_wec_cents"] = ((out["WEC_WUE_avg"] / L_PER_KGAL) * out["water_dollars_per_kgal"] * 100).round(3)
    if (out["effective_water_AE"] - out["_eff_ae_cents"]).abs().max() > 0.001:
        issues.append("effective_water_AE does not match (AE_WUE_avg/L_PER_KGAL)*water_dollars_per_kgal*100 (¢/kWh IT) for some rows.")
    else:
        print("  Effective water AE (¢/kWh IT): formula verified.")
    if (out["effective_water_WEC"] - out["_eff_wec_cents"]).abs().max() > 0.001:
        issues.append("effective_water_WEC does not match formula (¢/kWh IT) for some rows.")
    else:
        print("  Effective water WEC (¢/kWh IT): formula verified.")
    out = out.drop(columns=["_eff_ae_cents", "_eff_wec_cents"])

    # 3) Rollup: every county in CSV exists in rollup; mean WUE matches
    if rollup_path.is_file():
        print(f"Loading rollup: {rollup_path}")
        rollup = pd.read_csv(rollup_path, low_memory=False)
        rollup["county_fips"] = rollup["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        rollup_agg = rollup.groupby("county_fips", as_index=False).agg(
            AE_WUE_rollup=("AE_WUE", "mean"),
            WEC_WUE_rollup=("WEC_WUE", "mean"),
        )
        merged = out.merge(rollup_agg, on="county_fips", how="left")
        missing = merged["AE_WUE_rollup"].isna()
        if missing.any():
            issues.append(f"Counties in CSV not found in rollup: {out.loc[missing, 'county_fips'].tolist()[:10]}{'...' if missing.sum() > 10 else ''}")
        else:
            print("  All CSV county_fips present in rollup.")
        wue_ae_diff = (merged["AE_WUE_avg"] - merged["AE_WUE_rollup"]).abs()
        wue_wec_diff = (merged["WEC_WUE_avg"] - merged["WEC_WUE_rollup"]).abs()
        if wue_ae_diff.max() > 1e-5:
            bad = merged[wue_ae_diff > 1e-5]
            issues.append(f"AE_WUE_avg mismatch vs rollup for {len(bad)} counties (e.g. FIPS {bad['county_fips'].iloc[0]})")
        else:
            print("  AE_WUE_avg matches rollup mean.")
        if wue_wec_diff.max() > 1e-5:
            bad = merged[wue_wec_diff > 1e-5]
            issues.append(f"WEC_WUE_avg mismatch vs rollup for {len(bad)} counties.")
        else:
            print("  WEC_WUE_avg matches rollup mean.")
        # Rollup county list: any county in rollup missing from CSV?
        rollup_fips = set(rollup["county_fips"].unique())
        csv_fips = set(out["county_fips"].unique())
        only_rollup = rollup_fips - csv_fips
        if only_rollup:
            print(f"  Note: {len(only_rollup)} counties in rollup are not in CSV (OK if CSV is subset).")
    else:
        print("  Rollup not used (missing).")

    # 4) Optional: DuckDB county/FIPS check
    if args.db is not None and Path(args.db).is_file():
        try:
            import duckdb
            con = duckdb.connect(str(args.db))
            # Common pattern: county or geography table with fips, state
            try:
                db_counties = con.execute("SELECT * FROM information_schema.tables WHERE table_schema = 'main'").fetchdf()
                tables = db_counties["table_name"].tolist() if "table_name" in db_counties.columns else []
            except Exception:
                tables = []
            if tables:
                print(f"  DuckDB tables: {tables[:15]}...")
            # Try to find a table with county/fips/state
            for t in tables:
                try:
                    cols = con.execute(f"DESCRIBE {t}").fetchdf()
                    col_list = cols["column_name"].str.lower().tolist() if "column_name" in cols.columns else []
                    if "fips" in str(col_list).lower() or "county_fips" in str(col_list).lower():
                        sample = con.execute(f"SELECT * FROM {t} LIMIT 5").fetchdf()
                        print(f"  Found table {t} with FIPS-like columns; sample columns: {list(sample.columns)}")
                        break
                except Exception:
                    continue
            con.close()
        except ImportError:
            print("  DuckDB not installed; skipping DB check.")
        except Exception as e:
            print(f"  DuckDB check failed: {e}")
    else:
        if args.db is not None:
            print(f"  DuckDB file not found: {args.db}")
        else:
            print("  Optional: pass --db /path/to/amplytico.duckdb to cross-check with database.")

    # Summary
    print()
    if issues:
        print("ISSUES FOUND:")
        for i in issues:
            print("  -", i)
    else:
        print("All checks passed. CSV lines up with rollup and pricing.")


if __name__ == "__main__":
    main()
