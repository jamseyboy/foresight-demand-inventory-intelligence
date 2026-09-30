"""
Project FORESIGHT — Risk Scoring & Decisioning
=================================================
Combines the demand forecast with the current inventory position to score
stockout and overstock risk for every SKU, per Section 08 of the brief.

Run:
    python -m src.risk

Outputs:
    data/processed/risk_scores.csv   (one row per SKU: risk levels, action, rupee at stake)
"""
from pathlib import Path
import pandas as pd
import numpy as np

PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def score_risk(forecast: pd.DataFrame, weekly: pd.DataFrame, sku_master_path: Path = None) -> pd.DataFrame:
    """
    Stockout risk: projected stock over lead time vs. demand forecast over that same window.
    Overstock risk: on-hand stock vs. forecast demand over a forward window (here: full horizon).
    """
    latest = weekly.sort_values("week_start").groupby("sku_id").last().reset_index()
    latest = latest[["sku_id", "on_hand_units", "on_order_units", "lead_time_days",
                      "safety_stock", "reorder_point", "unit_cost", "list_price", "category"]]

    # total forecast demand over the full horizon, and over the lead-time window specifically
    fc = forecast.copy()
    fc["horizon_step"] = fc.groupby("sku_id").cumcount() + 1

    total_forecast = fc.groupby("sku_id")["forecast_units"].sum().rename("forecast_total_horizon")

    def lead_time_demand(row_sku_id, lead_time_days):
        weeks_of_lead = max(1, round(lead_time_days / 7))
        sub = fc[(fc["sku_id"] == row_sku_id) & (fc["horizon_step"] <= weeks_of_lead)]
        return sub["forecast_units"].sum()

    risk = latest.merge(total_forecast, on="sku_id", how="left")
    risk["forecast_lead_time_demand"] = risk.apply(
        lambda r: lead_time_demand(r["sku_id"], r["lead_time_days"]), axis=1
    )

    # --- stockout risk ---
    risk["projected_stock_at_end_of_lead_time"] = (
        risk["on_hand_units"] + risk["on_order_units"] - risk["forecast_lead_time_demand"]
    )
    risk["stockout_gap"] = risk["safety_stock"] - risk["projected_stock_at_end_of_lead_time"]
    max_gap = risk["stockout_gap"].clip(lower=0).max() or 1
    risk["stockout_risk"] = (risk["stockout_gap"].clip(lower=0) / max_gap).clip(0, 1)

    # --- overstock risk ---
    risk["excess_units"] = (risk["on_hand_units"] - risk["forecast_total_horizon"]).clip(lower=0)
    max_excess = risk["excess_units"].max() or 1
    risk["overstock_risk"] = (risk["excess_units"] / max_excess).clip(0, 1)

    # --- rupee value at stake ---
    risk["sales_at_risk_rupees"] = (
        risk["stockout_gap"].clip(lower=0) * risk["list_price"]
    )
    risk["capital_locked_rupees"] = risk["excess_units"] * risk["unit_cost"]

    # --- quadrant + recommended action (Section 08.2) ---
    def quadrant(row):
        stockout_high = row["stockout_risk"] >= 0.5
        overstock_high = row["overstock_risk"] >= 0.5
        if stockout_high and overstock_high:
            return "Watch / Volatile", "Investigate — demand is erratic; review manually."
        if stockout_high:
            return "Reorder Now", "Raise a replenishment order before stock runs out."
        if overstock_high:
            return "Markdown / Clear", "Promote or discount to free up capital."
        return "Healthy", "No action needed; leave as is."

    risk[["risk_quadrant", "recommended_action"]] = risk.apply(
        lambda r: pd.Series(quadrant(r)), axis=1
    )

    risk["rupees_at_stake"] = risk["sales_at_risk_rupees"] + risk["capital_locked_rupees"]

    cols = [
        "sku_id", "category", "on_hand_units", "on_order_units", "lead_time_days",
        "forecast_lead_time_demand", "forecast_total_horizon",
        "stockout_risk", "overstock_risk", "risk_quadrant", "recommended_action",
        "sales_at_risk_rupees", "capital_locked_rupees", "rupees_at_stake",
    ]
    return risk[cols].sort_values("rupees_at_stake", ascending=False).reset_index(drop=True)


def run():
    forecast = pd.read_csv(PROC_DIR / "forecast_latest.csv", parse_dates=["horizon_week"])
    weekly = pd.read_csv(PROC_DIR / "analysis_ready_weekly.csv", parse_dates=["week_start"])
    risk = score_risk(forecast, weekly)
    risk.to_csv(PROC_DIR / "risk_scores.csv", index=False)
    print(f"Risk scores written -> {PROC_DIR / 'risk_scores.csv'} ({len(risk)} SKUs)")
    print(risk["risk_quadrant"].value_counts())
    print(f"Total rupees at stake: {risk['rupees_at_stake'].sum():,.0f}")


if __name__ == "__main__":
    run()
