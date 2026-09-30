# Data-Quality Report — Project FORESIGHT

Findings from profiling the four raw extracts, and how each was handled.

- **Duplicate rows:** 0 duplicate `(date, sku_id)` rows in sales_daily; 0 in inventory_snapshots. Resolved by dropping duplicates, keeping the first occurrence.
- **Orphan SKUs in inventory_snapshots:** 150 of 200 SKU codes in inventory_snapshots (e.g. ['SKU051', 'SKU052', 'SKU053']...) have no matching record in sku_master or sales_daily. These cannot be forecast or scored (no sales history, no cost/price data) and are **dropped from scope** — treated as a client data-completeness issue to flag back, not fabricated around.
- **Inventory is monthly, not daily/weekly:** only 24 distinct snapshot dates over the ~2-year history (one per calendar month). Risk scoring therefore uses the most recent snapshot on or before the forecast date, carried forward — an approximation the client should be told about, since true intra-month stock movement isn't visible.
- **Negative-margin SKUs:** 16 of 50 SKUs are priced below cost (e.g. SKU002: cost 3867 vs. price 3806). Flagged as a pricing data-quality/business issue for the client — not treated as invalid data and not altered, since it may reflect an intentional loss-leader.
- **Calendar nulls:** `holiday` is null on 723 of 731 days and `promotion_event` is null on 656 days. These are expected (most days aren't holidays or promo events) and are filled with `'None'` rather than dropped.
- **Zero-sales days:** 0.6% of SKU-days have zero units sold — real signal for low-velocity SKUs, kept as-is rather than treated as missing.
- **Incomplete final week:** sales history ends on 2025-12-31 (Wednesday), so the last ISO week has only 3 of 7 days. Left in, it looks like a ~60% demand crash and corrupts training and backtests. Resolved by dropping any week without all 7 days.
