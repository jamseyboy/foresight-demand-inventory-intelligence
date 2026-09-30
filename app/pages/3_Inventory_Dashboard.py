"""Inventory Dashboard — what we hold, what's on order, and how long it will last."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (setup, header, get_data, category_filter, skus_in, rupees, num, chart_layout,
                   stock_table, stock_as_of, CHART_COLORS)

setup("Inventory", "🏬")
data = get_data()
header("Inventory Dashboard", "🏬", "How much stock we hold, what is on order, and how many weeks it will last.")

cat = category_filter(data)
t = stock_table(data)
t = t[t["sku_id"].isin(skus_in(data, cat))]
status_opts = ["All", "Low — below reorder point", "High — more than 12 weeks of stock", "OK"]
pick = st.sidebar.selectbox("Stock status", status_opts)
if pick != "All":
    t = t[t["stock_status"] == pick]
st.info(f"Stock levels are from the latest inventory count on **{stock_as_of(data)}**. "
        "Inventory in the source data is only updated monthly, so real stock today may differ.")
if t.empty:
    st.warning("No products match these filters.")
    st.stop()

# ---------------- headline numbers
c1, c2, c3, c4 = st.columns(4)
c1.metric("Units in stock", num(t["on_hand_units"].sum()))
c2.metric("Units on order", num(t["on_order_units"].sum()), help="Ordered from suppliers but not yet received.")
c3.metric("Value of stock (at cost)", rupees(t["stock_value"].sum()))
c4.metric("Products below reorder point", int(t["stock_status"].str.startswith("Low").sum()),
          help="Stock on hand is under the level that should trigger a new order.")

# ---------------- stock vs expected demand by category
st.subheader("Stock vs. expected sales, by category")
g = t.groupby("category", as_index=False).agg(Stock=("on_hand_units", "sum"), OnOrder=("on_order_units", "sum"),
                                              Expected=("forecast_8wk", "sum"))
g = g.melt("category", var_name="What", value_name="units")
g["What"] = g["What"].map({"Stock": "In stock now", "OnOrder": "On order", "Expected": "Expected sales (next 8 weeks)"})
fig = px.bar(g, x="category", y="units", color="What", barmode="group",
             color_discrete_map={"In stock now": CHART_COLORS[0], "On order": CHART_COLORS[4],
                                 "Expected sales (next 8 weeks)": CHART_COLORS[2]})
fig.update_layout(xaxis_title="", yaxis_title="Units")
st.plotly_chart(chart_layout(fig), width="stretch")
st.caption("If the yellow bar is taller than the other two combined, that category is heading for a shortage.")

# ---------------- least cover + value over time
left, right = st.columns(2)
with left:
    st.subheader("Products that will run out first")
    low = t.nsmallest(12, "weeks_of_cover").sort_values("weeks_of_cover", ascending=False)
    fig = px.bar(low, x="weeks_of_cover", y="label", orientation="h", color_discrete_sequence=[CHART_COLORS[3]])
    fig.update_layout(xaxis_title="Weeks of stock left (incl. on order)", yaxis_title="")
    st.plotly_chart(chart_layout(fig, 400, False), width="stretch")
with right:
    st.subheader("Value of stock over time")
    inv = data["inventory"].merge(data["sku"][["sku_id", "unit_cost"]], on="sku_id")
    inv = inv[inv["sku_id"].isin(t["sku_id"])]
    inv["value"] = inv["on_hand_units"] * inv["unit_cost"]
    g = inv.groupby("date", as_index=False)["value"].sum()
    fig = px.line(g, x="date", y="value", markers=True, color_discrete_sequence=[CHART_COLORS[0]])
    fig.update_layout(xaxis_title="Monthly count date", yaxis_title="Stock value at cost (₹)")
    st.plotly_chart(chart_layout(fig, 400, False), width="stretch")

# ---------------- table
st.subheader("Every product")
show = t.sort_values("weeks_of_cover")[["label", "category", "on_hand_units", "on_order_units", "reorder_point",
                                       "lead_time_days", "avg_weekly_forecast", "weeks_of_cover", "stock_status"]]
st.dataframe(show, hide_index=True, width="stretch", column_config={
    "label": "Product", "category": "Category",
    "on_hand_units": st.column_config.NumberColumn("In stock", format="%d"),
    "on_order_units": st.column_config.NumberColumn("On order", format="%d"),
    "reorder_point": st.column_config.NumberColumn("Reorder point", format="%d"),
    "lead_time_days": st.column_config.NumberColumn("Delivery time (days)", format="%d"),
    "avg_weekly_forecast": st.column_config.NumberColumn("Expected sales / week", format="%.0f"),
    "weeks_of_cover": st.column_config.NumberColumn("Weeks of stock", format="%.1f"),
    "stock_status": "Status"})
