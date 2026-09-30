"""Demand Forecast — how much we expect to sell over the next 8 weeks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils import (setup, header, get_data, category_filter, skus_in, num, chart_layout,
                   accuracy, pct, CHART_COLORS)

setup("Demand Forecast", "📈")
data = get_data()
header("Demand Forecast", "📈", "How many units of each product we expect to sell over the next 8 weeks.")

cat = category_filter(data)
skus = skus_in(data, cat)
choice = st.sidebar.selectbox("Product", ["All products in this category"] + [data["label"][s] for s in skus])
if choice == "All products in this category":
    sel = skus
    title = "All products" if cat == "All categories" else f"All {cat} products"
else:
    sel = [s for s in skus if data["label"][s] == choice]
    title = choice

weekly, fc = data["weekly"], data["forecast"]
hist = weekly[weekly["sku_id"].isin(sel)].groupby("week_start", as_index=False)["units_sold"].sum().tail(26)
f = fc[fc["sku_id"].isin(sel)].groupby("horizon_week", as_index=False)[["forecast_units", "forecast_low", "forecast_high"]].sum()
if hist.empty or f.empty:
    st.warning("No forecast is available for this selection.")
    st.stop()

# ---------------- headline numbers
recent_avg = hist["units_sold"].tail(8).mean()
fc_avg = f["forecast_units"].mean()
change = fc_avg / recent_avg - 1 if recent_avg else 0
peak = f.loc[f["forecast_units"].idxmax()]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Expected sales, next 8 weeks", num(f["forecast_units"].sum()) + " units")
c2.metric("Expected per week", num(fc_avg) + " units")
c3.metric("Compared with last 8 weeks", f"{change:+.0%}", help="Expected weekly sales vs. the average of the last 8 actual weeks.")
c4.metric("Busiest expected week", peak["horizon_week"].strftime("%d %b"), help=f"About {num(peak['forecast_units'])} units.")

# ---------------- chart
st.subheader(title)
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist["week_start"], y=hist["units_sold"], mode="lines+markers",
                         name="What we sold", line=dict(color="#5A6072")))
fig.add_trace(go.Scatter(x=list(f["horizon_week"]) + list(f["horizon_week"])[::-1],
                         y=list(f["forecast_high"]) + list(f["forecast_low"])[::-1], fill="toself",
                         fillcolor="rgba(75,63,191,0.15)", line=dict(color="rgba(0,0,0,0)"),
                         name="Likely range", hoverinfo="skip"))
fig.add_trace(go.Scatter(x=f["horizon_week"], y=f["forecast_units"], mode="lines+markers",
                         name="What we expect to sell", line=dict(color=CHART_COLORS[0], width=3)))
fig.update_layout(xaxis_title="Week starting", yaxis_title="Units per week")
st.plotly_chart(chart_layout(fig, 420), width="stretch")
st.caption("Grey = actual weekly sales. Purple = forecast. The shaded area is a rough ±25% range, "
           "not a precise statistical band. The forecast assumes no promotions or holidays in these weeks.")

# ---------------- table
st.subheader("Week-by-week forecast")
tbl = f.rename(columns={"horizon_week": "Week starting", "forecast_units": "Expected units",
                        "forecast_low": "Low estimate", "forecast_high": "High estimate"}).copy()
tbl["Week starting"] = tbl["Week starting"].dt.strftime("%d %b %Y")
for c in ["Expected units", "Low estimate", "High estimate"]:
    tbl[c] = tbl[c].round(0).astype(int)
st.dataframe(tbl, hide_index=True, width="stretch")

# ---------------- accuracy
st.subheader("How reliable is this forecast?")
acc = accuracy(data)
if acc is None:
    st.info("Accuracy results are not available yet. Run `python -m src.forecast` to create them.")
else:
    m, b, imp, by_h, bias = acc
    st.markdown(f"On weeks the model had **never seen**, it was off by about **{pct(m)}** on average, "
                f"about **{pct(imp)} better** than the simple rule *“sell what we sold this week last year”* "
                f"({pct(b)} off). In other words, roughly {m * 100:.0f} units off in every 100.")
    bh = by_h.melt("horizon", var_name="Method", value_name="err")
    bh["Method"] = bh["Method"].map({"model_wape": "FORESIGHT forecast", "baseline_wape": "Same week last year"})
    import plotly.express as px
    fig = px.bar(bh, x="horizon", y="err", color="Method", barmode="group",
                 color_discrete_map={"FORESIGHT forecast": CHART_COLORS[0], "Same week last year": "#B8BDCC"})
    fig.update_layout(xaxis_title="How many weeks ahead", yaxis_title="Average error (lower is better)",
                      yaxis_tickformat=".0%")
    st.plotly_chart(chart_layout(fig, 320), width="stretch")
    st.caption(f"The forecast is not better every single week: at week 3 the two methods are about equal. "
               f"It also tends to run slightly low ({abs(bias):.1f} units per product per week), so keep a small buffer on key items.")
