# Model Backtest Report — Project FORESIGHT

Rolling-origin backtest over 4 origins, forecast horizon = 8 weeks, evaluated with WAPE (Weighted Absolute Percentage Error).

**Overall WAPE — model: 0.098  |  seasonal-naive baseline: 0.114**

**Verdict: The model beats the seasonal-naive baseline** (a 14.3% reduction in WAPE vs. baseline).

## WAPE by forecast horizon (weeks ahead)

| Horizon (weeks) | Model WAPE | Baseline WAPE |
|---|---|---|
| 1 | 0.097 | 0.107 |
| 2 | 0.091 | 0.106 |
| 3 | 0.106 | 0.104 |
| 4 | 0.095 | 0.113 |
| 5 | 0.094 | 0.117 |
| 6 | 0.100 | 0.117 |
| 7 | 0.102 | 0.126 |
| 8 | 0.100 | 0.124 |

## Bias (signed mean error — positive = over-forecasting)
- Model bias: -2.35 units
- Baseline bias: 0.14 units

## Method notes
- Rolling-origin cross-validation: each origin trains only on weeks strictly before it (expanding window) — never a random split.
- Direct multi-horizon: a separate LightGBM model is trained per horizon step (1-8 weeks ahead), each using only features available as of the origin week — no future data enters a feature at any horizon.
- Seasonal-naive baseline predicts the same week's demand from approximately one year earlier (or the 8-week rolling mean where a year-ago value isn't available).