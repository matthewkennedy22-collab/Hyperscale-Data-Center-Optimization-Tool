"""
Add a county_fill_hex column to the drought CSV so each county_fips has a consistent
light fill color (same palette + lightening as the app's County column styling).
Reads the CSV, assigns each unique county_fips a color, and writes the result.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

# Same palette as app (ui.PLOTLY_COLORWAY); same lighten as _utils.lighten_hex
PLOTLY_COLORWAY = [
    "#0e7490", "#ea580c", "#059669", "#dc2626", "#7c3aed", "#b45309",
]


def lighten_hex(hex_color, factor=0.88):
    hex_color = (hex_color or "#cccccc").lstrip("#")
    if len(hex_color) != 6:
        return "#f5f5f5"
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(255 * (1 - factor) + r * factor))
    g = min(255, int(255 * (1 - factor) + g * factor))
    b = min(255, int(255 * (1 - factor) + b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def main():
    parser = argparse.ArgumentParser(description="Add county_fill_hex column to drought CSV.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="Path to drought CSV (default: project root drought_weekly_by_county_2015_2024_week52only.csv)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output path (default: same as input, overwrites)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    default_csv = project_root / "drought_weekly_by_county_2015_2024_week52only.csv"
    csv_path = Path(args.csv_path) if args.csv_path else default_csv
    out_path = Path(args.output) if args.output else csv_path

    if not csv_path.is_file():
        print(f"Error: not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    if "county_fips" not in pd.read_csv(csv_path, nrows=1).columns:
        print("Error: CSV has no county_fips column.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {csv_path} ...")
    df = pd.read_csv(csv_path, dtype={"county_fips": str})
    df["county_fips"] = df["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)

    fips_ordered = sorted(df["county_fips"].unique())
    fips_to_fill = {
        fips: lighten_hex(PLOTLY_COLORWAY[i % len(PLOTLY_COLORWAY)])
        for i, fips in enumerate(fips_ordered)
    }
    df["county_fill_hex"] = df["county_fips"].map(fips_to_fill)

    print(f"Writing {len(df)} rows to {out_path} (unique counties: {len(fips_ordered)}) ...")
    df.to_csv(out_path, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
