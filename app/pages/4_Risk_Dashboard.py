"""Risk Dashboard — which products will run out, and which are overstocked."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (setup, header, get_data, category_filter, skus_in, rupees, chart_layout,
                   COLORS, ICONS, MEANING, stock_as_of)

setup("Risk Dashboard", "⚠️")
data = get_data()
header("Risk Dashboard", "⚠️", "Which products are about to run out, and which are overstocked, ranked by money at stake.")

cat = category_filter(data)
r = data["risk"].copy()
r = r[r["sku_id"].isin(skus_in(data, cat))]
if r.empty:
    st.warning("No products match this selection.")
    st.stop()
r["Product"] = r["sku_id"].map(data["label"])

# ---------------- headline numbers
counts = r["risk_quadrant"].value_counts()
cols = st.columns(4)
for col, q in zip(cols, ["Reorder Now", "Markdown / Clear", "Watch / Volatile", "Healthy"]):
    col.metric(f"{ICONS[q]} {q}", int(counts.get(q, 0)), help=MEANING[q])
c1, c2 = st.columns(2)
c1.metric("Sales at risk (products in view)", rupees(r["sales_at_risk_rupees"].sum()),
          help="Sales we could lose if products run out before new stock arrives.")
c2.metric("Cash tied up in extra stock (products in view)", rupees(r["capital_locked_rupees"].sum()),
          help="Cost of stock beyond what we expect to sell in the next 8 weeks.")
st.caption(f"Based on the 8-week forecast and stock counted on {stock_as_of(data)}.")

# ---------------- grid
st.subheader("All products at a glance")
with st.expander("How to read this chart"):
    st.markdown("Each bubble is a product. **Higher** means more likely to run out. **Further right** means more "
                "stock than we need. **Bigger** means more money at stake. Bottom-left (green) is where we want to be.")
r["size"] = r["rupees_at_stake"].clip(lower=r["rupees_at_stake"].max() * 0.03 + 1)
fig = px.scatter(r, x="overstock_risk", y="stockout_risk", color="risk_quadrant", size="size", size_max=38,
                 hover_name="Product", color_discrete_map=COLORS,
                 hover_data={"size": False, "risk_quadrant": False, "overstock_risk": ":.2f", "stockout_risk": ":.2f"},
                 labels={"overstock_risk": "Too much stock  →", "stockout_risk": "Likely to run out  →",
                         "risk_quadrant": "Group"})
for x0, y0, colr, txt, ax in [(0, 0.5, "rgba(214,69,69,0.06)", "REORDER NOW", "left"),
                              (0.5, 0.5, "rgba(232,163,23,0.08)", "WATCH", "right"),
                              (0, 0, "rgba(59,165,93,0.06)", "HEALTHY", "left"),
                              (0.5, 0, "rgba(59,130,196,0.06)", "MARKDOWN / CLEAR", "right")]:
    fig.add_shape(type="rect", x0=x0, y0=y0, x1=x0 + 0.5, y1=y0 + 0.5 if y0 == 0.5 else 0.5,
                  fillcolor=colr, line=dict(width=0), layer="below")
    fig.add_annotation(x=x0 + (0.01 if ax == "left" else 0.49), y=y0 + (0.47 if y0 == 0.5 else 0.47),
                       text=txt, showarrow=False, xanchor=ax, font=dict(size=11, color="#5A6072"))
fig.update_xaxes(range=[-0.05, 1.05], showgrid=False)
fig.update_yaxes(range=[-0.05, 1.05])
st.plotly_chart(chart_layout(fig, 480), width="stretch")

# ---------------- action lists
st.subheader("What to do")
def show(frame, money_col, money_label):
    if frame.empty:
        st.success("Nothing to do here. No products fall in this group.")
        return
    out = frame.sort_values(money_col, ascending=False)[
        ["Product", "category", "on_hand_units", "on_order_units", "lead_time_days",
         "forecast_lead_time_demand", money_col, "recommended_action"]]
    st.dataframe(out, hide_index=True, width="stretch", column_config={
        "category": "Category",
        "on_hand_units": st.column_config.NumberColumn("In stock", format="%d"),
        "on_order_units": st.column_config.NumberColumn("On order", format="%d"),
        "lead_time_days": st.column_config.NumberColumn("Delivery time (days)", format="%d"),
        "forecast_lead_time_demand": st.column_config.NumberColumn("Expected sales before delivery", format="%.0f"),
        money_col: st.column_config.NumberColumn(money_label, format="₹%.0f"),
        "recommended_action": "What to do"})

t1, t2, t3 = st.tabs(["🔴 Reorder now", "🔵 Markdown / clear", "🟠 Watch closely"])
with t1:
    st.caption("Order these first. Sorted by sales we could lose.")
    show(r[r["risk_quadrant"] == "Reorder Now"], "sales_at_risk_rupees", "Sales at risk")
with t2:
    st.caption("Consider a promotion or discount. Sorted by cash tied up.")
    show(r[r["risk_quadrant"] == "Markdown / Clear"], "capital_locked_rupees", "Cash tied up")
with t3:
    st.caption("Demand is unpredictable for these. Review by hand.")
    show(r[r["risk_quadrant"] == "Watch / Volatile"], "rupees_at_stake", "Money at stake")

# ---------------- biggest exposures
st.subheader("Where the money is")
top = r.nlargest(10, "rupees_at_stake").sort_values("rupees_at_stake")
fig = px.bar(top, x="rupees_at_stake", y="Product", orientation="h", color="risk_quadrant", color_discrete_map=COLORS)
fig.update_layout(xaxis_title="Money at stake (₹)", yaxis_title="")
st.plotly_chart(chart_layout(fig, 400), width="stretch")
st.caption("Products marked green still show a small amount at stake, but it is below the level where we recommend action.")

st.download_button("⬇️ Download this list (CSV)", r.drop(columns=["size"]).to_csv(index=False).encode(),
                   "foresight_risk_scores.csv", "text/csv")

with st.expander("How the risk is worked out"):
    st.markdown(
        "- **Running out:** we add up the sales we expect *before new stock could arrive* (the delivery time). "
        "If stock in hand plus stock on order would not cover that and the safety cushion, the product is flagged.\n"
        "- **Too much stock:** we compare stock in hand with everything we expect to sell in the next 8 weeks. "
        "Anything above that is extra.\n"
        "- **Money at stake:** lost sales use the selling price; extra stock uses what we paid for it.\n"
        "- **Scores from 0 to 1** are relative to the other products today. A product moves to a red or blue "
        "group when its score is 0.5 or higher.")
