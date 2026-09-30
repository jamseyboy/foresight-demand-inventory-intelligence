"""Executive Summary — the headline numbers and what to do this week."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (setup, header, get_data, rupees, num, pct, chart_layout, accuracy, key_insights,
                   stock_as_of, data_through, COLORS, ICONS)

setup("Executive Summary", "📋")
data = get_data()
header("Executive Summary", "📋", "The money at stake, what to do this week, and how much to trust the numbers.")

r = data["risk"].copy()
r["Product"] = r["sku_id"].map(data["label"])
re_ = r[r["risk_quadrant"] == "Reorder Now"].sort_values("sales_at_risk_rupees", ascending=False)
md = r[r["risk_quadrant"] == "Markdown / Clear"].sort_values("capital_locked_rupees", ascending=False)
watch = r[r["risk_quadrant"] == "Watch / Volatile"]

sales_risk, cash_locked = r["sales_at_risk_rupees"].sum(), r["capital_locked_rupees"].sum()
st.success(
    f"Over the next 8 weeks, about **{rupees(sales_risk)}** of sales are at risk from products running out, and "
    f"**{rupees(cash_locked)}** of cash is tied up in extra stock. "
    f"**{len(re_) + len(md) + len(watch)} of {len(r)} products** need attention; the rest are healthy.")

# ---------------- headline numbers
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sales at risk", rupees(sales_risk), help="All products.")
c2.metric("…in products to reorder now", rupees(re_["sales_at_risk_rupees"].sum()), help=f"{len(re_)} products.")
c3.metric("Cash tied up in extra stock", rupees(cash_locked), help="All products.")
c4.metric("…in products to discount", rupees(md["capital_locked_rupees"].sum()), help=f"{len(md)} products.")

# ---------------- what to do
st.subheader("What to do this week")
left, right = st.columns(2)
with left:
    st.markdown(f"##### {ICONS['Reorder Now']} Reorder now")
    if re_.empty:
        st.success("No products need an urgent reorder.")
    else:
        st.dataframe(re_[["Product", "category", "sales_at_risk_rupees"]], hide_index=True, width="stretch",
                     column_config={"category": "Category",
                                    "sales_at_risk_rupees": st.column_config.NumberColumn("Sales at risk", format="₹%.0f")})
with right:
    st.markdown(f"##### {ICONS['Markdown / Clear']} Discount or clear")
    if md.empty:
        st.success("No products are heavily overstocked.")
    else:
        st.dataframe(md[["Product", "category", "capital_locked_rupees"]], hide_index=True, width="stretch",
                     column_config={"category": "Category",
                                    "capital_locked_rupees": st.column_config.NumberColumn("Cash tied up", format="₹%.0f")})
if not watch.empty:
    st.warning("Review by hand (demand is unpredictable): " + ", ".join(watch["Product"]))

top = r.nlargest(8, "rupees_at_stake").sort_values("rupees_at_stake")
fig = px.bar(top, x="rupees_at_stake", y="Product", orientation="h", color="risk_quadrant", color_discrete_map=COLORS)
fig.update_layout(xaxis_title="Money at stake (₹)", yaxis_title="")
st.plotly_chart(chart_layout(fig, 360, legend=True), width="stretch")

# ---------------- reliability
st.subheader("How much can we trust the forecast?")
acc = accuracy(data)
if acc:
    m, b, imp, _, bias = acc
    st.markdown(f"Tested on weeks the model had never seen, the forecast was off by about **{pct(m)}**, versus "
                f"**{pct(b)}** for the simple rule “same week as last year”. That is about **{pct(imp)} more accurate**. "
                f"It is not better every week (about equal at the 3-week mark) and it runs slightly low, "
                f"so keep a small buffer on your most important products.")
else:
    st.info("Accuracy results are not available yet. Run `python -m src.forecast`.")

# ---------------- findings & limits
left, right = st.columns(2)
with left:
    st.subheader("What we found")
    for line in key_insights(data):
        st.markdown(f"- {line}")
with right:
    st.subheader("Things to keep in mind")
    st.markdown(
        f"- **Stock counts are monthly.** The latest is from {stock_as_of(data)}, while sales run to {data_through(data)}. "
        "A fresh count would sharpen this list.\n"
        "- **No promotions or holidays are assumed** for the forecast weeks. If you plan a promotion, expect sales above the forecast.\n"
        "- **The forecast range is approximate** (about ±25%), not a precise statistical interval.\n"
        "- **Money figures are estimates**: lost sales use the selling price; extra stock uses cost.")

st.download_button("⬇️ Download the action list (CSV)",
                   pd.concat([re_, md, watch])[["Product", "category", "risk_quadrant", "recommended_action",
                                                 "sales_at_risk_rupees", "capital_locked_rupees"]].to_csv(index=False).encode(),
                   "foresight_action_list.csv", "text/csv")
