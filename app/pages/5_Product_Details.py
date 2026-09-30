"""Product Details — everything about one product on one page."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils import (setup, header, get_data, category_filter, skus_in, rupees, num, chart_layout,
                   stock_table, stock_as_of, COLORS, ICONS, MEANING, CHART_COLORS)

setup("Product Details", "🔍")
data = get_data()
header("Product Details", "🔍", "Pick a product to see its price, sales, forecast, stock and recommended action.")

cat = category_filter(data)
skus = skus_in(data, cat)
if not skus:
    st.warning("No products in this category.")
    st.stop()
label = st.sidebar.selectbox("Product", [data["label"][s] for s in skus])
sid = next(s for s in skus if data["label"][s] == label)

sku = data["sku"].set_index("sku_id").loc[sid]
rk = data["risk"].set_index("sku_id").loc[sid]
stk = stock_table(data).set_index("sku_id").loc[sid]
wk = data["weekly"][data["weekly"]["sku_id"] == sid].sort_values("week_start")
fc = data["forecast"][data["forecast"]["sku_id"] == sid].sort_values("horizon_week")
dl = data["daily"][data["daily"]["sku_id"] == sid]

# ---------------- identity
q = rk["risk_quadrant"]
st.subheader(f"{sku['product_name']}  ·  {sid}")
st.caption(f"{sku['category']} › {sku['subcategory']}  |  First sold {sku['launch_date']:%d %b %Y}")
st.markdown(f"### {ICONS[q]} {q}")
st.write(MEANING[q])
st.info(f"**Recommended action:** {rk['recommended_action']}")

# ---------------- price & profit
st.markdown("#### Price and profit")
margin = sku["gross_margin_per_unit"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Selling price", f"₹{sku['list_price']:,.0f}")
c2.metric("Cost to us", f"₹{sku['unit_cost']:,.0f}")
c3.metric("Profit per unit", f"₹{margin:,.0f}")
c4.metric("Profit margin", f"{margin / sku['list_price']:.0%}")
if margin < 0:
    st.warning("This product sells for **less than it costs**. Check whether that is intended (for example a loss-leader).")

# ---------------- sales
st.markdown("#### Sales")
promo = dl.groupby("promo_flag")["units_sold"].mean()
boost = (promo[1] / promo[0] - 1) if (0 in promo.index and 1 in promo.index and promo[0] > 0) else None
cat_rank = data["weekly"][data["weekly"]["category"] == sku["category"]].groupby("sku_id")["units_sold"].sum() \
    .rank(ascending=False).get(sid)
n_cat = data["weekly"][data["weekly"]["category"] == sku["category"]]["sku_id"].nunique()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Units sold (all time)", num(wk["units_sold"].sum()))
c2.metric("Revenue (all time)", rupees(wk["revenue"].sum()))
c3.metric("Rank in category", f"#{int(cat_rank)} of {n_cat}", help="By total units sold.")
c4.metric("Promotion boost", f"{boost:+.0%}" if boost is not None else "n/a")

hist = wk.tail(52)
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist["week_start"], y=hist["units_sold"], name="What we sold", mode="lines",
                         line=dict(color="#5A6072")))
if not fc.empty:
    fig.add_trace(go.Scatter(x=list(fc["horizon_week"]) + list(fc["horizon_week"])[::-1],
                             y=list(fc["forecast_high"]) + list(fc["forecast_low"])[::-1], fill="toself",
                             fillcolor="rgba(75,63,191,0.15)", line=dict(color="rgba(0,0,0,0)"),
                             name="Likely range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc["horizon_week"], y=fc["forecast_units"], name="What we expect to sell",
                             mode="lines+markers", line=dict(color=CHART_COLORS[0], width=3)))
fig.update_layout(xaxis_title="Week starting", yaxis_title="Units per week")
st.plotly_chart(chart_layout(fig, 380), width="stretch")
if not fc.empty:
    st.caption(f"Expected to sell about **{num(fc['forecast_units'].sum())} units** over the next 8 weeks "
               f"(roughly {num(fc['forecast_units'].mean())} a week).")

# ---------------- stock & risk
left, right = st.columns(2)
with left:
    st.markdown("#### Stock")
    st.caption(f"Counted on {stock_as_of(data)}")
    a, b = st.columns(2)
    a.metric("In stock", num(stk["on_hand_units"]))
    b.metric("On order", num(stk["on_order_units"]))
    a.metric("Delivery time", f"{int(stk['lead_time_days'])} days")
    b.metric("Reorder point", num(stk["reorder_point"]), help="Order more when stock falls below this.")
    a.metric("Safety cushion", num(stk["safety_stock"]), help="Extra stock kept in case demand is higher than expected.")
    b.metric("Weeks of stock", f"{stk['weeks_of_cover']:.1f}", help="In stock plus on order, at the expected sales pace.")
with right:
    st.markdown("#### Risk")
    st.write("**Chance of running out**")
    st.progress(float(rk["stockout_risk"]), text=f"{rk['stockout_risk']:.0%} (relative to other products)")
    st.write("**Chance of holding too much**")
    st.progress(float(rk["overstock_risk"]), text=f"{rk['overstock_risk']:.0%} (relative to other products)")
    a, b = st.columns(2)
    a.metric("Sales at risk", rupees(rk["sales_at_risk_rupees"]))
    b.metric("Cash tied up in extra stock", rupees(rk["capital_locked_rupees"]))
    st.caption(f"Expected sales before a new order could arrive: about {num(rk['forecast_lead_time_demand'])} units.")
