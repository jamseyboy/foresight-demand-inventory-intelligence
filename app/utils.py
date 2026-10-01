"""Shared helpers for the FORESIGHT Streamlit app (data loading, formatting, plain-language text)."""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import os


docker_data_path = os.getenv("DATA_PATH")
print(f"Using data path: {docker_data_path}")

if docker_data_path:
    PROC = Path(docker_data_path + "/processed")
    print(f"Using data from utils path: {PROC}")
    for item in PROC.iterdir():
        print(item)
        if item.is_dir():
            print(item.name)
else:
    ROOT = Path(__file__).resolve().parents[1]
    PROC = ROOT / "data" / "processed"

# ---- plain-language labels for the four risk groups (Section 08 of the brief) ----
COLORS = {"Reorder Now": "#D64545", "Markdown / Clear": "#3B82C4",
          "Watch / Volatile": "#E8A317", "Healthy": "#3BA55D"}
ICONS = {"Reorder Now": "🔴", "Markdown / Clear": "🔵", "Watch / Volatile": "🟠", "Healthy": "🟢"}
MEANING = {
    "Reorder Now": "Likely to run out before new stock arrives. Place an order.",
    "Markdown / Clear": "Holding much more than we expect to sell. Promote or discount it.",
    "Watch / Volatile": "Both risks are high. Demand is erratic, so review it by hand.",
    "Healthy": "Stock matches expected demand. No action needed.",
}
CHART_COLORS = ["#4B3FBF", "#3BA55D", "#E8A317", "#D64545", "#3B82C4", "#8E6BBF", "#2A9D8F", "#F4845F"]

REQUIRED = ["daily", "weekly", "forecast", "risk", "inventory", "sku"]


def setup(title: str, icon: str) -> None:
    """Page config + light styling. Call first on every page."""
    st.set_page_config(page_title=f"{title} · FORESIGHT", page_icon=icon, layout="wide")
    st.markdown(
        """<style>
        [data-testid="stMetric"] {background:#F5F6FA;border:1px solid #E3E5EC;border-radius:10px;padding:14px 16px;}
        [data-testid="stMetricLabel"] p {font-size:0.9rem;color:#5A6072;}
        .block-container {padding-top:2rem;}
        </style>""", unsafe_allow_html=True)
    st.sidebar.markdown("**FORESIGHT**  \nNorthBay Living · Demand & Inventory Planning")


def header(title: str, icon: str, purpose: str) -> None:
    st.title(f"{icon} {title}")
    st.markdown(f"_{purpose}_")


@st.cache_data(show_spinner="Loading data…")
def _load_all() -> dict:
    def rd(name, **kw):
        p = PROC / name
        return pd.read_csv(p, **kw) if p.exists() else None
    return {
        "daily": rd("analysis_ready_daily.csv", parse_dates=["date", "launch_date"]),
        "weekly": rd("analysis_ready_weekly.csv", parse_dates=["week_start"]),
        "forecast": rd("forecast_latest.csv", parse_dates=["horizon_week"]),
        "risk": rd("risk_scores.csv"),
        "inventory": rd("inventory_clean.csv", parse_dates=["date"]),
        "sku": rd("sku_master_clean.csv", parse_dates=["launch_date"]),
        "backtest": rd("backtest_results.csv", parse_dates=["origin"]),
    }


def get_data() -> dict:
    """Load everything; show a friendly message (and stop) if the pipeline hasn't been run."""
    data = _load_all()
    missing = [k for k in REQUIRED if data.get(k) is None]
    if missing:
        st.error("The data files are not ready yet.")
        st.info("Run these three commands from the project folder, then refresh this page:\n\n"
                "`python -m src.pipeline`  →  `python -m src.forecast`  →  `python -m src.risk`")
        st.stop()
    sku = data["sku"].copy()
    sku["label"] = sku["product_name"] + " · " + sku["sku_id"]
    data["sku"] = sku
    data["label"] = dict(zip(sku["sku_id"], sku["label"]))
    data["name"] = dict(zip(sku["sku_id"], sku["product_name"]))
    return data


# ---------------------------------------------------------------- formatting
def rupees(x) -> str:
    x = float(x)
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} crore"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.1f} lakh"
    return f"₹{x:,.0f}"


def num(x) -> str:
    return f"{float(x):,.0f}"


def pct(x, digits=0) -> str:
    return f"{float(x) * 100:.{digits}f}%"


def category_filter(data: dict, key="cat") -> str:
    cats = ["All categories"] + sorted(data["sku"]["category"].unique().tolist())
    return st.sidebar.selectbox("Category", cats, key=key)


def skus_in(data: dict, category: str) -> list:
    sku = data["sku"]
    if category != "All categories":
        sku = sku[sku["category"] == category]
    return sorted(sku["sku_id"].tolist())


def chart_layout(fig, height=380, legend=True):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), showlegend=legend,
                      plot_bgcolor="white", legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#ECEEF3")
    return fig


# ---------------------------------------------------------------- shared calculations
def stock_table(data: dict) -> pd.DataFrame:
    """Latest stock position per SKU, joined with forecast demand and weeks of cover."""
    inv = data["inventory"].sort_values("date").groupby("sku_id").last().reset_index()
    fc = data["forecast"].groupby("sku_id")["forecast_units"].agg(avg_weekly_forecast="mean",
                                                                  forecast_8wk="sum").reset_index()
    t = inv.merge(data["sku"][["sku_id", "product_name", "category", "unit_cost", "label"]], on="sku_id") \
           .merge(fc, on="sku_id", how="left")
    t["weeks_of_cover"] = (t["on_hand_units"] + t["on_order_units"]) / t["avg_weekly_forecast"].replace(0, np.nan)
    t["stock_value"] = t["on_hand_units"] * t["unit_cost"]

    def status(r):
        if r["on_hand_units"] < r["reorder_point"]:
            return "Low — below reorder point"
        if r["weeks_of_cover"] > 12:
            return "High — more than 12 weeks of stock"
        return "OK"
    t["stock_status"] = t.apply(status, axis=1)
    return t


def accuracy(data: dict):
    """Return (model_error, baseline_error, improvement, by_horizon_df) or None if no backtest saved."""
    bt = data.get("backtest")
    if bt is None or bt.empty:
        return None
    w = bt["n_obs"]
    m = np.average(bt["model_wape"], weights=w)
    b = np.average(bt["baseline_wape"], weights=w)
    by_h = bt.groupby("horizon")[["model_wape", "baseline_wape"]].mean().reset_index()
    bias = bt["model_bias"].mean()
    return m, b, 1 - m / b, by_h, bias


def stock_as_of(data: dict) -> str:
    return data["inventory"]["date"].max().strftime("%d %b %Y")


def data_through(data: dict) -> str:
    return data["daily"]["date"].max().strftime("%d %b %Y")


def key_insights(data: dict) -> list:
    """Plain-language findings computed from the data (used on Sales and Executive pages)."""
    w, d, sku = data["weekly"], data["daily"], data["sku"]
    out = []
    tot = w.groupby("week_start")["units_sold"].sum()
    by_month = w.assign(m=w["week_start"].dt.month).groupby("m")["units_sold"].sum() / \
        w.assign(m=w["week_start"].dt.month).groupby("m")["week_start"].nunique()
    months = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July",
              8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
    out.append(f"Sales are seasonal: **{months[by_month.idxmax()]}** is the busiest month and "
               f"**{months[by_month.idxmin()]}** the quietest (about {by_month.max() / by_month.min() - 1:.0%} higher).")
    st_ = w.groupby("sku_id")["units_sold"].sum().sort_values(ascending=False)
    out.append(f"A few products carry the business: the **top 10 of {len(st_)} products** make up "
               f"**{st_.head(10).sum() / st_.sum():.0%}** of units sold; the bottom 10 only {st_.tail(10).sum() / st_.sum():.0%}.")
    promo = w.groupby("promo_flag")["units_sold"].mean()
    if 0 in promo.index and 1 in promo.index:
        out.append(f"Promotions work: weeks with a promotion sell **{promo[1] / promo[0] - 1:.0%} more** per product than weeks without.")
    below = int((sku["gross_margin_per_unit"] < 0).sum())
    if below:
        out.append(f"**{below} of {len(sku)} products are priced below their cost.** Worth a pricing review.")
    return out
