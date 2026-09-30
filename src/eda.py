from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
FIG_DIR = REPORT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def run():
    w = pd.read_csv(PROC_DIR / "analysis_ready_weekly.csv", parse_dates=["week_start"])

    # --- overall weekly demand trend ---
    total = w.groupby("week_start")["units_sold"].sum()
    plt.figure(figsize=(10, 4))
    total.plot()
    plt.title("Total weekly units sold — all SKUs")
    plt.ylabel("Units")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "total_weekly_demand.png")
    plt.close()

    # --- demand by category ---
    cat = w.groupby(["week_start", "category"])["units_sold"].sum().unstack()
    plt.figure(figsize=(10, 5))
    cat.plot(ax=plt.gca())
    plt.title("Weekly demand by category")
    plt.ylabel("Units")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "demand_by_category.png")
    plt.close()

    # --- top movers / dead stock ---
    sku_totals = w.groupby("sku_id")["units_sold"].sum().sort_values(ascending=False)
    top10 = sku_totals.head(10)
    bottom10 = sku_totals.tail(10)

    plt.figure(figsize=(8, 5))
    top10.plot(kind="barh", color="seagreen")
    plt.title("Top 10 SKUs by total units sold")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "top10_skus.png")
    plt.close()

    plt.figure(figsize=(8, 5))
    bottom10.plot(kind="barh", color="indianred")
    plt.title("Bottom 10 SKUs by total units sold (dead-stock candidates)")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "bottom10_skus.png")
    plt.close()

    # --- promo effect ---
    promo_effect = w.groupby("promo_flag")["units_sold"].mean()

    # --- seasonality ---
    w["week_start"] = pd.to_datetime(w["week_start"])
    w["month"] = w["week_start"].dt.month
    seasonal = w.groupby("month")["units_sold"].mean()
    plt.figure(figsize=(8, 4))
    seasonal.plot(kind="bar", color="steelblue")
    plt.title("Average weekly units sold by month (seasonality)")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "seasonality_by_month.png")
    plt.close()

    # --- holiday effect ---
    holiday_effect = w.groupby("is_holiday")["units_sold"].mean()

    # --- coefficient of variation per SKU (volatility) ---
    cv = w.groupby("sku_id")["units_sold"].agg(["mean", "std"])
    cv["cv"] = cv["std"] / cv["mean"]
    most_volatile = cv.sort_values("cv", ascending=False).head(5)

    # Build the insight memo
    # Year-over-year on the same calendar weeks (avoids mistaking seasonality for a trend)
    y24, y25 = total[total.index.year == 2024], total[total.index.year == 2025]
    n = min(len(y24), len(y25))
    growth_pct = (y25.iloc[:n].sum() / y24.iloc[:n].sum() - 1) * 100

    memo = f"""# Data-Quality & EDA Insight Memo — Project FORESIGHT

## Data quality
See `reports/data_quality.md` for the full report. Headline: sales_daily and sku_master are clean and
consistent (50 SKUs, 2 years of daily history, no duplicates); inventory_snapshots contains 150 orphan
SKU codes with no corresponding master/sales data (dropped from scope) and is only refreshed monthly
rather than daily.

## Demand patterns

1. **Demand is strongly seasonal but flat year over year.** Comparing the same {n} weeks of 2025 vs
   2024, total units changed by {growth_pct:+.1f}%. Volume peaks in roughly Feb-Jun and dips in
   Aug-Dec, so a seasonal signal (lag_52, month) matters more than a trend term.
   (A naive "first 8 weeks vs last 8 weeks" comparison would wrongly show a decline, because it
   compares peak season with off-season.)

2. **Category mix is uneven.** {cat.mean().idxmax()} averages the highest weekly volume of the five
   categories tracked ({cat.mean().max():.0f} units/week), while {cat.mean().idxmin()} averages the
   lowest ({cat.mean().min():.0f} units/week) — worth checking whether slower categories are
   under-marketed or genuinely lower-demand.

3. **Top and bottom movers are concentrated, not spread evenly.** The top 10 SKUs
   ({', '.join(top10.index[:3])}, ...) account for {top10.sum() / sku_totals.sum() * 100:.0f}% of
   total units sold across all 50 SKUs, while the bottom 10
   ({', '.join(bottom10.index[:3])}, ...) account for only
   {bottom10.sum() / sku_totals.sum() * 100:.0f}%. The bottom group are dead-stock candidates worth
   flagging for markdown regardless of what the forecast says.

4. **Promotions lift average weekly demand** from {promo_effect.get(0, 0):.1f} units/week (no promo)
   to {promo_effect.get(1, 0):.1f} units/week (promo active) — a
   {(promo_effect.get(1, 0) / max(promo_effect.get(0, 0), 1) - 1) * 100:.0f}% lift. Promo history is a
   necessary feature for the forecast, not an optional one.

5. **Holidays move demand too** — average weekly units on holiday weeks is {holiday_effect.get(1, 0):.1f}
   vs. {holiday_effect.get(0, 0):.1f} on non-holiday weeks. Calendar features (holiday flag, month,
   season) belong in the model.

6. **Demand volatility varies sharply by SKU.** The most volatile SKUs by coefficient of variation
   ({', '.join(most_volatile.index[:3])}) swing far more week to week than the median SKU — these are
   the SKUs most likely to land in the "Watch / Volatile" quadrant of the risk grid and need manual
   review rather than pure automation.

## Charts
See `reports/figures/`: total_weekly_demand.png, demand_by_category.png, top10_skus.png,
bottom10_skus.png, seasonality_by_month.png.
"""
    (REPORT_DIR / "eda_insights.md").write_text(memo)
    print(f"Wrote {REPORT_DIR / 'eda_insights.md'} and 5 charts to {FIG_DIR}")


if __name__ == "__main__":
    run()
