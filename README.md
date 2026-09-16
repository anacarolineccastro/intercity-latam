# LATAM Intercity Dashboard

A Streamlit dashboard for weekly Brazil and Mexico Intercity performance. It
combines Finance, Reserve Rate, Return Rate, and Sessions query exports without
requiring direct warehouse access.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Weekly refresh

1. Run the four supplied queries with the desired `start_date`, `end_date`, and
   Intercity `vvid` values.
2. Export each final result as CSV or XLSX.
3. Open **Data refresh** in the dashboard.
4. Download a template if you need to check the expected columns.
5. Upload each export and review its row count, date coverage, and preview.
6. Choose **append** to add or update weeks, or **replace** to replace that
   dataset completely.
7. Save. The app stores normalized parquet files under `data/stored/`.

Append mode de-duplicates rows at each dataset's natural weekly grain, keeping
the newest uploaded version. Upload metadata and date coverage are recorded in
`data/stored/manifest.json`.

## Pages and metrics

- **Overview:** Requests, trips, conversion, gross bookings, variable
  contribution, VC margin, weekly trends, and the session-to-trip funnel.
- **Routes:** Ranked route volume, conversion, finance, distance, and exports.
- **Reserve:** Completion, reliability, booking lead time, trends, and details.
- **Supply & return:** Return rate, time to return, and no-attempt measures.

All ratio calculations are guarded against zero denominators. Because source
files are already aggregated, the app sums additive fields and calculates
ratios only after aggregation.

## Input contracts

Blank, valid examples live in `data/templates/`. Required columns are also
shown beside every uploader. Optional query columns are retained and available
in downloaded filtered data.

The source queries label monetary columns with `_usd`, although their Finance
CTE converts values with plan FX rates. Confirm the intended currency before
sharing financial results; the dashboard preserves the supplied column labels.

## Test

```bash
pytest
```
