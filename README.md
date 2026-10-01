# Project FORESIGHT — Demand & Inventory Intelligence

Zidio Development internship engagement · Client: NorthBay Living

## About

This is a Data Science Project initiated by Zidio, prepared by Batch 6.2 Team no 10.

This project is for a period of 4 weeks ~ 1 month starting from `3rd September 2026 - 3rd October 2026`.

**A working forecasting and risk system:** a reproducible pipeline, an 8-week-ahead SKU-level demand
forecast (LightGBM, backtested against a seasonal-naive baseline), stockout/overstock risk scoring,
a Streamlit planning dashboard, and a FastAPI scoring service.


## The problem

NorthBay Living stocks by gut feel: best-sellers run out, slow movers pile up. This project turns
their sales/inventory history into a weekly forecast and an early-warning system telling the ops
team what to reorder, what to clear, and what to leave alone.

## Headline result

**The model beats the seasonal-naive baseline by ~14% (WAPE 0.098 vs. 0.114)** on a rolling-origin
backtest — see `reports/model_backtest.md` for the full breakdown by horizon, and
`reports/executive_readout.md` for the business summary.

## Quickstart

**Note:** Before starting or running the project make sure the raw `*.csv` files follow proper column name and structure.
go here -> [Raw Data Model](data/DATA_STRUCTURE.md)


```bash
pip install -r requirements.txt

# 1. Clean + join the four raw extracts
python -m src.pipeline

# 2. Exploratory analysis -> reports/eda_insights.md + charts
python -m src.eda
```
```bash
# 3. Train + backtest the forecast model, generate the forward forecast
python -m src.forecast
```

*running `python -m src.forecast` may throw error due to missing `'libomp.dylib'` library, this need system 
level installation of the libomp library.*
*In **macos** you can install the library by running `'brew install libomp'`.*

```bash
# 4. Score stockout/overstock risk for every SKU
python -m src.risk

# 5. Launch the planning dashboard
streamlit run app/Home_Page.py

# 6. Launch the scoring API (separate terminal)
uvicorn service.main:app --reload --port 8000
```

Re-running steps 1–4 end-to-end reproduces every number in this README from the raw CSVs in
`data/raw/`.



## Repository structure

```
foresight/
  data/raw/                 four input extracts (sales_daily, sku_master, calendar, inventory_snapshots)
  data/processed/           analysis-ready datasets, forecast, risk scores, trained models
  notebooks                 Code blocks in jupyter notebook to visualize and run methods use in the source.
  src/
    pipeline.py             ingest -> validate -> clean -> merge -> weekly aggregation
    eda.py                  exploratory analysis + insight memo
    features.py             leakage-free feature engineering (lags, rolling stats, calendar, promo)
    forecast.py             seasonal-naive baseline + LightGBM direct multi-horizon model + backtest
    risk.py                 stockout/overstock scoring, decisioning grid, rupee impact
  app/                      Streamlit multipage planning dashboard
    Home_Page.py            landing page (run this one)
    utils.py                shared data loading, formatting, plain-language text
    pages/1_Sales_Analytics.py            what sold, when, top and slowest products
    pages/2_Demand_Forcast.py             8-week forecast, week-by-week table, accuracy
    pages/3_Inventory_Dashboard.py        stock, on order, weeks of cover
    pages/4_Risk_Dashboard.py             reorder / markdown lists and risk grid
    pages/5_Product_Details.py            one product on one page
    pages/6_Executive_Summary_Dashboard.py  headline numbers and actions
  service/main.py           FastAPI scoring service
  reports/                  data_quality.md, eda_insights.md, model_backtest.md, executive_readout.md, figures/
```

## Data

Four extracts, joined on `(date, sku_id)`: `sales_daily` (daily units/revenue/price/promo),
`sku_master` (category, cost, price), `calendar` (season, holiday, promo events), and
`inventory_snapshots` (monthly stock position, lead time, reorder point). See
`reports/data_quality.md` for issues found and how each was handled — including 150 orphan SKU
codes in the inventory extract with no matching sales/master record, and the monthly (not
daily/weekly) inventory refresh cadence.

## Methodology (Section 07 of the engagement brief)

Frame the metric (WAPE) → build a seasonal-naive baseline → engineer features → train a model →
**rolling-origin backtest, never a random split** → compare to baseline honestly → risk-score.
Every feature at week *t* uses only data available before *t* — verified by construction, not just
asserted (see `src/features.py`).

## Risk scoring (Section 08)

Stockout risk compares forecast demand over the lead-time window against on-hand + on-order stock.
Overstock risk compares on-hand stock against forecast demand over the full 8-week horizon. Each SKU
lands in one of four quadrants — Reorder Now, Markdown / Clear, Watch / Volatile, Healthy — with a
rupee value attached so the team can prioritize.


## Run locally with Docker Compose

```bash
docker compose up --build
```
This builds one image and starts both services from it: the dashboard at
http://localhost:8501 and the API at http://localhost:8000 (interactive docs at
http://localhost:8000/docs). `data/processed/` is mounted read-only from your machine, so
re-running `python -m src.pipeline && python -m src.forecast && python -m src.risk` on the host and
refreshing the dashboard picks up new numbers without rebuilding the image.

```bash
docker compose down          # stop and remove both containers
docker compose logs -f api   # tail one service's logs
```

## Deploy to Render:
1. Push this repo to GitHub, with `data/processed/*.csv` committed (the deployed containers read
   these directly; they do not re-run the pipeline). `data/raw/*.csv` and `models.pkl` are
   intentionally excluded — see `.gitignore`.
2. In the Render dashboard: **New → Blueprint**, point it at this repo. Render reads `render.yaml`
   and creates both `foresight-dashboard` and `foresight-api` automatically.
3. Each gets a URL like `https://foresight-dashboard.onrender.com` and
   `https://foresight-api.onrender.com`.

**Free-tier limitations to know about:** both services spin down after 15 minutes of inactivity and
take 30-60 seconds to wake on the next request — fine for a demo/portfolio link, not for something
that needs to always respond instantly. Streamlit's dashboard relies on a WebSocket connection,
which Render's free tier does support (confirmed in their docs), so the dashboard itself isn't
broken by the free tier — only slowed by the cold start.

## Scoring API

```
GET  /skus                  -> list of scoreable SKU ids
GET  /forecast/{sku_id}      -> 8-week forecast with uncertainty band
GET  /risk/{sku_id}          -> risk quadrant, scores, recommended action, rupees at stake
POST /score/batch {"sku_ids": ["SKU001","SKU002"]}
```

Unknown SKUs return a `404` with a clear message rather than crashing.

## Known limitations (reported honestly, not hidden)

- At horizon week 3 the model and baseline are essentially tied; the model slightly under-forecasts
  overall (bias about -2 units per SKU-week).
- Future promo/holiday values are assumed to be 0 (the calendar ends 2025-12-31), and the forecast
  band is a fixed +/-25%, not a calibrated interval.
- The final, incomplete week of sales (29-31 Dec 2025) is dropped in the pipeline.
- Inventory position is monthly in the source data; risk scores use the latest available snapshot,
  which can lag true stock by up to ~3 weeks.
- 16 of 50 SKUs are priced below cost in `sku_master` — flagged, not corrected, since it may be
  intentional (loss-leader) pricing.

## Reproducibility

Every number in this README and the executive readout comes from re-running `pipeline.py` →
`eda.py` → `forecast.py` → `risk.py` against `data/raw/`. Random seeds are fixed
(`random_state=42`) for the model.
