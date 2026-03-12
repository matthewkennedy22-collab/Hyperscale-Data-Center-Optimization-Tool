# Deploying the dashboard (e.g. Streamlit Community Cloud)

To deploy on **Streamlit Community Cloud**, your app must be in a **GitHub repository**. You cannot deploy directly from a local folder.

## GitHub’s 100 MB file limit

GitHub **rejects any file over 100 MB**. Your project has several much larger files (multi‑GB DuckDB, CSVs, Tableau extracts). Those should **not** be committed.

- **Do not put in the repo:**  
  `amplytico.duckdb`, `FINAL_counties_with_pue_wue.csv`, `weather_hourly_with_counties.csv`, large `.hyper` files, etc.  
  They are listed in the project root `.gitignore`.

- **Safe to put in the repo (if small enough):**  
  - All code under `Dashboard Tool/` (and any small config).  
  - `pricing/pricing_by_state.csv` (small).  
  - `data/county_week_rollup.csv` and `data/counties.csv` **only if** the built rollup is under 100 MB (often it is).  
  - `drought_weekly_by_county_2015_2024_week52only.csv` is ~91 MB — under 100 MB, so it can be committed if you want the Drought Risk page to work without external data.

## Options for large or borderline files

1. **Keep them out of the repo (recommended for multi‑GB files)**  
   Use the root `.gitignore` so these never get committed. Build the rollup and other artifacts locally (or in CI) and either:  
   - Host them elsewhere (see below), or  
   - Only deploy with a smaller/sample dataset that fits in the repo.

2. **Git LFS (for single files roughly 100 MB–2 GB)**  
   [Git LFS](https://git-lfs.github.com/) stores large files on GitHub’s LFS server instead of in the repo.  
   - Install Git LFS, then: `git lfs install`, `git lfs track "*.csv"` (or specific paths), commit the `.gitattributes` and the files.  
   - Note: GitHub gives limited free LFS storage and bandwidth; very large or many files can hit those limits.

3. **Host data elsewhere and load by URL**  
   Put the built rollup (and optionally drought CSV) on:  
   - **Cloud storage:** e.g. S3, Google Cloud Storage, or Azure Blob (public or signed URLs).  
   - **GitHub Releases:** upload `county_week_rollup.csv` (and others) as release assets; use the “latest release” asset URL in the app.  
   - **Other:** Dropbox, OneDrive, etc., with a direct download link.  
   Then change the app to load from a URL when the local file is missing (e.g. via `pandas.read_csv(url)` or a small download step). This keeps the repo small and avoids GitHub size limits.

4. **Use a small dataset in the repo**  
   Build a rollup from a subset of counties (or one year) so that `county_week_rollup.csv` is under 100 MB. Commit that so the deployed app runs with “demo” data without external URLs.

## Suggested flow for Streamlit Community Cloud

1. Create a new GitHub repo (or use an existing one).
2. In the repo, put **only** what’s needed to run the app:  
   - The `Dashboard Tool` app (e.g. under a `Dashboard Tool/` or `app/` folder).  
   - Root-level `pricing/` (or the path your app expects).  
   - Root-level `data/` with `county_week_rollup.csv` and `counties.csv` **if** they are under 100 MB; otherwise host them and add URL loading.  
   - Optionally `drought_weekly_by_county_2015_2024_week52only.csv` if you want Drought Risk and it’s under 100 MB.  
   - A root `requirements.txt` if Streamlit Cloud expects it at repo root (e.g. `streamlit>=1.28.0` and other deps from `Dashboard Tool/requirements.txt`).
3. In Streamlit Cloud: “New app” → connect the repo, set **Main file path** to e.g. `Dashboard Tool/Home.py`, and (if needed) set **Working directory** so that paths like `data/`, `pricing/` resolve correctly.
4. Deploy. If you use URL-based loading for large data, set the base URL (or full URLs) in the app’s **Secrets** or environment variables so the app can fetch the files at startup.

**Drought data via Secrets (recommended when the CSV is not in the repo):**  
In Streamlit Cloud: **Manage app → Settings → Secrets**, add a key `drought_csv_url` (or `DROUGHT_CSV_URL`) with the full URL to the drought CSV (e.g. a direct download link from Google Drive, S3, or GitHub Releases). The app will load drought from this URL when the local file is not present.

## Summary

- **Yes:** You need the app (and any data it needs) in a GitHub repo to deploy on Streamlit Community Cloud.  
- **Large files:** Do not commit files over 100 MB. Use `.gitignore`, Git LFS for borderline sizes, or host data elsewhere and load by URL.  
- **Practical approach:** Commit only code + small/sample data; host `county_week_rollup.csv` (and other large assets) on cloud storage or Releases and have the app load from a URL when the file isn’t present locally.
