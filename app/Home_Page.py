"""FORESIGHT — landing page.  Run:  streamlit run app/Home_Page.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from utils import setup, get_data, rupees, num, stock_as_of, data_through, MEANING, ICONS

setup("Home", "📦")
data = get_data()
risk = data["risk"]

st.title("📦 FORESIGHT")
st.subheader("Know what to reorder, what to clear, and what to leave alone.")
st.write("This tool turns NorthBay Living's own sales and stock records into a simple weekly plan. "
         "It estimates how much of each product will sell over the next 8 weeks, "
         "then checks that against the stock you hold today.")

st.markdown("### This week at a glance")
n_re = int((risk["risk_quadrant"] == "Reorder Now").sum())
n_md = int((risk["risk_quadrant"] == "Markdown / Clear").sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("🔴 Products to reorder", n_re, help="Likely to run out before new stock arrives.")
c2.metric("🔵 Products to discount", n_md, help="Far more stock than we expect to sell.")
c3.metric("Sales at risk", rupees(risk["sales_at_risk_rupees"].sum()),
          help="Sales we could lose if low-stock products run out (all products).")
c4.metric("Cash tied up in extra stock", rupees(risk["capital_locked_rupees"].sum()),
          help="Cost of stock beyond what we expect to sell in 8 weeks (all products).")
st.caption(f"Sales data through {data_through(data)} · Stock levels as of {stock_as_of(data)} · "
           f"{len(risk)} products tracked")

st.markdown("### Where to go")
pages = [
    ("pages/6_Executive_Summary_Dashboard.py", "📋 Executive Summary", "Start here. The headline numbers and what to do this week."),
    ("pages/4_Risk_Dashboard.py", "⚠️ Risk Dashboard", "Which products will run out, and which are overstocked."),
    ("pages/2_Demand_Forcast.py", "📈 Demand Forecast", "How much of each product we expect to sell in the next 8 weeks."),
    ("pages/3_Inventory_Dashboard.py", "🏬 Inventory", "How much stock we hold, what is on order, and how long it will last."),
    ("pages/1_Sales_Analytics.py", "💰 Sales Analytics", "What sold, when, and which products and categories lead."),
    ("pages/5_Product_Details.py", "🔍 Product Details", "Everything about one product on a single page."),
]
cols = st.columns(3)
for i, (path, label, blurb) in enumerate(pages):
    with cols[i % 3]:
        with st.container(border=True):
            st.page_link(path, label=label)
            st.caption(blurb)

st.markdown("### What the four colours mean")
cols = st.columns(4)
for col, q in zip(cols, ["Reorder Now", "Markdown / Clear", "Watch / Volatile", "Healthy"]):
    col.markdown(f"**{ICONS[q]} {q}**")
    col.caption(MEANING[q])

with st.expander("Plain-language glossary"):
    st.markdown(
        "- **SKU**: one sellable product (for example SKU012).\n"
        "- **Stockout**: running out of a product, so sales are lost.\n"
        "- **Overstock**: holding much more than will sell, so cash is stuck and discounts may follow.\n"
        "- **Lead time**: days between placing an order and stock arriving.\n"
        "- **Reorder point**: the stock level at which a new order should be placed.\n"
        "- **Weeks of cover**: how many weeks current stock (plus stock on order) will last at the expected sales pace.\n"
        "- **Forecast error**: on average, how far off the forecast is. 10% means about 10 units off in every 100.")
