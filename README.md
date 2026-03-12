# Dashboard Tool — County Comparison & Cooling System Analysis

Streamlit app for **county-level comparison** of data-center cooling options: **Air Economizer (AE)** vs **Water Economizer (WEC)**. Shows PUE, WUE, effective costs (electric and water), weather impacts, drought risk, and pricing estimation (e.g. 1000 MW hyperscale).

All metrics use a **fixed IT load** (per unit); data is read from prebuilt rollups and state-level pricing.

---

## Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended)
- **pip** (or another Python package manager)

---

## Step-by-step: Get the app running with full data

### Step 1 — Get the code

Clone or download this repository so you have the **project root** (the folder that contains both `Dashboard Tool` and the `data` and `pricing` folders). For example:

```text
Counties+Zones Database/          ← project root (your working directory)
├── Dashboard Tool/
│   ├── Home.py
│   ├── pages/
│   ├── scripts/
│   ├── _utils.py
│   ├── ui.py
│   └── requirements.txt
├── data/                         ← rollup and optional files go here
├── pricing/                      ← pricing CSV goes here
└── ...
```

All commands below assume you are in the **project root** (`Counties+Zones Database`).

---

### Step 2 — Create a virtual environment (recommended)

```bash
cd "Counties+Zones Database"
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

---

### Step 3 — Install dependencies

```bash
pip install -r "Dashboard Tool/requirements.txt"
```

This installs Streamlit, pandas, and Plotly.

---

### Step 4 — Set up data (required for the app to run)

The app needs **three things** to start:

1. **County × week rollup** + county list  
2. **State-level pricing**  
3. **(Optional)** Drought file and county centroids for full features  

Choose **Path A** if you have the large source CSV; choose **Path B** if you only have (or will download) prebuilt files.

---

#### Path A — You have the source CSV (~4 GB)

If you have `FINAL_counties_with_pue_wue.csv` (hourly weather + PUE/WUE by county), build the rollup locally:

1. Place the large CSV in the parent folder of your project, or anywhere you can point to:
   - Default paths the script checks:  
     `../FINAL_counties_with_pue_wue.csv` or  
     `PUE WUE SIM/weather_hourly_with_counties_with_pue_wue.csv`

2. From the **project root**, run:

   ```bash
   python "Dashboard Tool/scripts/build_county_week_rollup.py"
   ```

   Or point to the file explicitly:

   ```bash
   python "Dashboard Tool/scripts/build_county_week_rollup.py" --input /path/to/FINAL_counties_with_pue_wue.csv --output data/county_week_rollup.csv
   ```

3. This writes:
   - `data/county_week_rollup.csv`
   - `data/counties.csv`

4. Ensure **pricing** is present (see Step 4B).

---

#### Path B — You use prebuilt or hosted data (no source CSV)

If you do **not** have the 4 GB source file, you need **prebuilt** rollup and county list from someone who ran the build (or from a hosted URL, if your app is set up to load from URL).

1. **Obtain and place these files:**

   | File | Where it must live | Purpose |
   |------|--------------------|--------|
   | `county_week_rollup.csv` | `data/county_week_rollup.csv` | County × week PUE, WUE, weather rollup (required) |
   | `counties.csv` | `data/counties.csv` | County list for sidebar (required) |
   | `pricing_by_state.csv` | `pricing/pricing_by_state.csv` | State electric/water rates (required) |

   Create the `data/` and `pricing/` folders if they do not exist.

2. **Pricing file format**  
   `pricing/pricing_by_state.csv` must include at least:  
   `state_full`, `state_abbr`, `electric_cents_per_kwh`, `water_dollars_per_kgal`  
   (and optionally `region`). If you only have the app repo, you must obtain this file from the project or create it from public state-rate data.

3. **Hosting prebuilt data (for deployment or sharing)**  
   - Put `county_week_rollup.csv` and `counties.csv` on cloud storage (e.g. S3, Google Cloud Storage) or GitHub Releases.  
   - Use **public** or **signed** URLs.  
   - To have the app load from URLs when local files are missing, you need a small code change (e.g. in `_utils.py`) to download from a configurable base URL; see `DEPLOY.md` for deployment and hosting notes.

---

### Step 4B — Pricing file (required)

- **Path:** `pricing/pricing_by_state.csv` (relative to project root).
- Must contain: `state_abbr`, `electric_cents_per_kwh`, `water_dollars_per_kgal` (and typically `state_full`).
- If you have this file in the project, ensure it is in the `pricing/` folder. If not, create or obtain it and place it there.

---

### Step 5 — Optional data (full implementation)

For **all** app features, add these when possible:

| File | Where it must live | Purpose |
|------|--------------------|--------|
| `drought_weekly_by_county_2015_2024_week52only.csv` | Project root | Drought Risk page (10-year weekly drought index) |
| `county_centroids.csv` | `data/county_centroids.csv` | Home page map (selected counties on a US map) |

- **Drought file**  
  Place the CSV in the **project root** (same level as `Dashboard Tool` and `data`). The app looks for:  
  `drought_weekly_by_county_2015_2024_week52only.csv`.  
  **When deploying (e.g. Streamlit Cloud):** If the file is not in the repo, set the secret **`drought_csv_url`** to the full URL of the CSV (Manage app → Settings → Secrets). The app will load drought from that URL when the local file is missing.

- **County centroids (map)**  
  From the project root, run:

  ```bash
  python "Dashboard Tool/scripts/fetch_county_centroids.py"
  ```

  This downloads Census data and writes `data/county_centroids.csv`. The app can also try to fetch centroids on first use if this file is missing.

---

### Step 6 — Verify required files

Before starting the app, confirm these exist:

**Required (app will not run without these):**

- `data/county_week_rollup.csv`
- `data/counties.csv`
- `pricing/pricing_by_state.csv`

**Optional (for full implementation):**

- `drought_weekly_by_county_2015_2024_week52only.csv` (in project root)
- `data/county_centroids.csv`

---

### Step 7 — Run the app

From the **project root**:

```bash
streamlit run "Dashboard Tool/Home.py"
```

Or from inside the app folder:

```bash
cd "Dashboard Tool"
streamlit run Home.py
```

The app still expects `data/` and `pricing/` relative to the **parent** of `Dashboard Tool`, so running from the project root is recommended.

Open the URL shown in the terminal (e.g. `http://localhost:8501`). Select one or more counties in the sidebar to use the dashboard.

---

## Quick reference: data files

| Path | Required? | Source |
|------|-----------|--------|
| `data/county_week_rollup.csv` | Yes | `build_county_week_rollup.py` (Path A) or prebuilt/hosted (Path B) |
| `data/counties.csv` | Yes | Same script as rollup, or with prebuilt rollup |
| `pricing/pricing_by_state.csv` | Yes | Project asset or create from state rates |
| `drought_weekly_by_county_2015_2024_week52only.csv` | No | Project asset or external; for Drought Risk page |
| `data/county_centroids.csv` | No | `fetch_county_centroids.py` or auto-download on first use |

---

## Deploying (e.g. Streamlit Community Cloud)

To deploy, the app must run from a **GitHub** repository. Large files (e.g. multi-GB CSVs) cannot be committed; use hosted data and optional URL loading. See **`DEPLOY.md`** in this folder for:

- GitHub’s 100 MB file limit and what to exclude
- Using Git LFS or external storage for large/prebuilt data
- Steps to deploy on Streamlit Community Cloud with data hosted elsewhere

---

## What the app includes

- **Home** — County selector and optional US map; link to other pages.
- **Weather impacts** — Weekly time series (temp, RH, pressure) and relation to PUE/WUE.
- **System comparison** — PUE and WUE by county (AE vs WEC); effective electric/water cost; charts over the year.
- **Drought risk** — 10-year weekly drought index and seasonal patterns (requires drought CSV).
- **Comparison insights** — Weighted composite scores and recommendations (power vs water vs drought).
- **Pricing estimation** — Annual utility cost for a fixed 1000 MW IT load (electric + water breakdown).

---

## Scripts (`Dashboard Tool/scripts/`)

| Script | Purpose |
|--------|--------|
| `build_county_week_rollup.py` | Build `county_week_rollup.csv` and `counties.csv` from the large hourly CSV (Path A). |
| `fetch_county_centroids.py` | Download Census county centroids → `data/county_centroids.csv` for the Home map. |
| `build_county_month_rollup.py` | Legacy month-level rollup (app prefers weekly). |
| `build_counties_wue_water_csv.py` | Build counties + WUE/water cost CSV from rollup + pricing. |
| `verify_counties_wue_water.py` | Verify WUE/water cost formulas against rollup and pricing. |

---

## Data sources and assumptions

- **Weather & PUE/WUE:** From thermodynamics-based model (Lei & Masanet); hourly data aggregated to county × week (or month) for this app.
- **Pricing:** State-level electric (¢/kWh) and water ($/kgal). Effective cost = PUE × electric rate (electric), WUE × water rate (water).
- **IT load:** Held constant (per unit) in the underlying simulation; results are per kWh of IT load.
- **Drought:** Weekly county-level index (e.g. 2015–2024) for risk and water-stress weighting.

For more on deployment and hosting large files, see **`DEPLOY.md`**.
