# Data-Quality & EDA Insight Memo — Project FORESIGHT

## Data quality
See `reports/data_quality.md` for the full report. Headline: sales_daily and sku_master are clean and
consistent (50 SKUs, 2 years of daily history, no duplicates); inventory_snapshots contains 150 orphan
SKU codes with no corresponding master/sales data (dropped from scope) and is only refreshed monthly
rather than daily.

## Demand patterns

1. **Demand is strongly seasonal but flat year over year.** Comparing the same 51 weeks of 2025 vs
   2024, total units changed by -0.3%. Volume peaks in roughly Feb-Jun and dips in
   Aug-Dec, so a seasonal signal (lag_52, month) matters more than a trend term.
   (A naive "first 8 weeks vs last 8 weeks" comparison would wrongly show a decline, because it
   compares peak season with off-season.)

2. **Category mix is uneven.** Home Decor averages the highest weekly volume of the five
   categories tracked (1270 units/week), while Furniture averages the
   lowest (789 units/week) — worth checking whether slower categories are
   under-marketed or genuinely lower-demand.

3. **Top and bottom movers are concentrated, not spread evenly.** The top 10 SKUs
   (SKU012, SKU045, SKU018, ...) account for 35% of
   total units sold across all 50 SKUs, while the bottom 10
   (SKU050, SKU003, SKU028, ...) account for only
   6%. The bottom group are dead-stock candidates worth
   flagging for markdown regardless of what the forecast says.

4. **Promotions lift average weekly demand** from 96.1 units/week (no promo)
   to 101.4 units/week (promo active) — a
   6% lift. Promo history is a
   necessary feature for the forecast, not an optional one.

5. **Holidays move demand too** — average weekly units on holiday weeks is 88.0
   vs. 98.9 on non-holiday weeks. Calendar features (holiday flag, month,
   season) belong in the model.

6. **Demand volatility varies sharply by SKU.** The most volatile SKUs by coefficient of variation
   (SKU011, SKU025, SKU039) swing far more week to week than the median SKU — these are
   the SKUs most likely to land in the "Watch / Volatile" quadrant of the risk grid and need manual
   review rather than pure automation.

## Charts
See `reports/figures/`: total_weekly_demand.png, demand_by_category.png, top10_skus.png,
bottom10_skus.png, seasonality_by_month.png.
