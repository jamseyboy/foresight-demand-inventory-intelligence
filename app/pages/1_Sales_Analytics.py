"""Sales Analytics — what sold, when, and which products lead."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (setup, header, get_data, category_filter, rupees, num, chart_layout,
                   key_insights, CHART_COLORS)

setup("Sales Analytics", "💰")
data = get_data()
header("Sales Analytics", "💰", "What has sold, when it sold, and which products and categories lead.")

daily = data["daily"]
cat = category_filter(data)
lo, hi = daily["date"].min().date(), daily["date"].max().date()
rng = st.sidebar.date_input("Date range", (lo, hi), min_value=lo, max_value=hi)
if len(rng) != 2:
    st.info("Pick both a start date and an end date in the sidebar.")
    st.stop()

df = daily[(daily["date"] >= pd.Timestamp(rng[0])) & (daily["date"] <= pd.Timestamp(rng[1]))]
if cat != "All categories":
    df = df[df["category"] == cat]
if df.empty:
    st.warning("No sales found for this selection. Try a wider date range or another category.")
    st.stop()

# ---------------- headline numbers
days = df["date"].nunique()
promo = df.groupby("promo_flag")["units_sold"].mean()
lift = (promo[1] / promo[0] - 1) if (0 in promo.index and 1 in promo.index and promo[0] > 0) else None
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total revenue", rupees(df["revenue"].sum()))
c2.metric("Units sold", num(df["units_sold"].sum()))
c3.metric("Units per week", num(df["units_sold"].sum() / days * 7), help="Average across the selected dates.")
c4.metric("Promotion boost", f"{lift:+.0%}" if lift is not None else "n/a",
          help="How much more a product sells on a promotion day than on a normal day.")

# ---------------- revenue over time
st.subheader("Revenue by month")
split = st.radio("Show", ["Total", "Split by category"], horizontal=True)
m = df.assign(month=df["date"].dt.to_period("M").dt.to_timestamp())
if split == "Total":
    g = m.groupby("month", as_index=False)["revenue"].sum()
    fig = px.bar(g, x="month", y="revenue", color_discrete_sequence=[CHART_COLORS[0]])
else:
    g = m.groupby(["month", "category"], as_index=False)["revenue"].sum()
    fig = px.bar(g, x="month", y="revenue", color="category", color_discrete_sequence=CHART_COLORS)
fig.update_layout(xaxis_title="", yaxis_title="Revenue (₹)")
st.plotly_chart(chart_layout(fig, legend=split != "Total"), width="stretch")
st.caption("The first and last months may be partial if you narrowed the date range.")

# ---------------- categories + seasonality
left, right = st.columns(2)
with left:
    st.subheader("Which categories earn the most?")
    g = df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue")
    fig = px.bar(g, x="revenue", y="category", orientation="h", color_discrete_sequence=[CHART_COLORS[0]])
    fig.update_layout(xaxis_title="Revenue (₹)", yaxis_title="")
    st.plotly_chart(chart_layout(fig, 340, False), width="stretch")
with right:
    st.subheader("Busy and quiet months")
    mm = m.groupby("month")["units_sold"].sum().reset_index()
    mm["name"] = mm["month"].dt.strftime("%b")
    mm["num"] = mm["month"].dt.month
    g = mm.groupby(["num", "name"], as_index=False)["units_sold"].mean().sort_values("num")
    fig = px.bar(g, x="name", y="units_sold", color_discrete_sequence=[CHART_COLORS[4]])
    fig.update_layout(xaxis_title="", yaxis_title="Average units sold in the month")
    st.plotly_chart(chart_layout(fig, 340, False), width="stretch")

# ---------------- top / bottom products
st.subheader("Best and slowest sellers")
p = df.groupby("sku_id", as_index=False).agg(units=("units_sold", "sum"), revenue=("revenue", "sum"))
p["Product"] = p["sku_id"].map(data["label"])
tab1, tab2 = st.tabs(["🏆 Top 10 by units", "🐌 Slowest 10 by units"])
for tab, frame, colr in [(tab1, p.nlargest(10, "units").sort_values("units"), CHART_COLORS[1]),
                         (tab2, p.nsmallest(10, "units").sort_values("units", ascending=False), CHART_COLORS[3])]:
    with tab:
        fig = px.bar(frame, x="units", y="Product", orientation="h", color_discrete_sequence=[colr])
        fig.update_layout(xaxis_title="Units sold", yaxis_title="")
        st.plotly_chart(chart_layout(fig, 380, False), width="stretch")
st.caption("Slow sellers are the first candidates to review for discounts or removal.")

# ---------------- promotion effect
st.subheader("Do promotions help?")
pr = df.groupby("promo_flag", as_index=False)["units_sold"].mean()
pr["When"] = pr["promo_flag"].map({0: "Normal day", 1: "Promotion day"})
fig = px.bar(pr, x="When", y="units_sold", color="When",
             color_discrete_map={"Normal day": "#B8BDCC", "Promotion day": CHART_COLORS[0]})
fig.update_layout(xaxis_title="", yaxis_title="Average units per product per day")
st.plotly_chart(chart_layout(fig, 300, False), width="stretch")

with st.expander("Key findings across all products and the full history"):
    for line in key_insights(data):
        st.markdown(f"- {line}")
