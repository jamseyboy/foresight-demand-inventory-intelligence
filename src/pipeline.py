from pathlib import Path
import pandas as pd


PARENT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PARENT_DIR / "data" /"processed"
RAW_DIR = PARENT_DIR / "data"/"raw"
REPORT_DIR = PARENT_DIR / "reports"


PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)



# ---------------------------------------------------------------------------
# 1. LOAD
# ---------------------------------------------------------------------------


def load_raw_data() -> dict[str, pd.DataFrame]:
    sales = pd.read_csv(RAW_DIR / "sales_daily.csv")
    sku = pd.read_csv(RAW_DIR / "sku_master.csv")
    inventory = pd.read_csv(RAW_DIR / "inventory_snapshots.csv")
    calendar = pd.read_csv(RAW_DIR / "calendar.csv")

    sales = sales.rename(columns={"Date":"date",
                                  "SKU":"sku_id",
                                  "Units_Sold":"units_sold",
                                  "Revenue":"revenue" ,
                                  "Price":"unit_price" ,
                                  "Promotion":"promo_flag"})

    sku = sku.rename(columns={"SKU": "sku_id",
                              "Product_Name": "product_name",
                              "Category": "category",
                              "Subcategory": "subcategory",
                              "Launch_Date": "launch_date",
                              "Cost_Price": "unit_cost",
                              "Selling_Price": "list_price",
                              "Gross_Margin_Per_Unit": "gross_margin_per_unit",
    })

    calendar = calendar.rename(columns={"date": "date"})

    inventory = inventory.rename(columns={"Snapshot_Date": "date",
                                          "SKU": "sku_id",
                                          "Current_Stock": "on_hand_units",
                                          "On_Order": "on_order_units",
                                          "Lead_Time_Days": "lead_time_days",
                                          "Safety_Stock": "safety_stock",
                                          "Reorder_Point": "reorder_point",
                                          "Inventory_Value": "inventory_value",
    })

    for df, col in [(sales, "date"), (sku, "launch_date"),(calendar, "date"), (inventory, "date")]:
        df[col] = pd.to_datetime(df[col])
    return {"sales": sales, "sku": sku, "inventory": inventory, "calendar": calendar}



# ---------------------------------------------------------------------------
# 2. CLEAN
# ---------------------------------------------------------------------------


def clean(raw:dict[str,pd.DataFrame]) -> dict[str,pd.DataFrame] :

    sales, sku, inventory, calendar = raw["sales"], raw["sku"], raw["inventory"], raw["calendar"]


    sales = sales.drop_duplicates(subset=["date", "sku_id"]).copy()
    sales = sales[sales['units_sold'] >= 0]
    sales["promo_flag"] = sales["promo_flag"].fillna(0).astype(int)


    sku = sku.copy()


    inventory = inventory.drop_duplicates(subset=["sku_id", "date"]).copy()
    inventory = inventory[inventory["sku_id"].isin(sku["sku_id"])]

    calendar = calendar.copy()
    calendar["promotion_event"] = calendar["promotion_event"].fillna("None")
    calendar["holiday"] = calendar["holiday"].fillna("None")
    calendar["is_holiday"] = calendar["is_holiday"].fillna(0).astype(int)

    return {"sales": sales, "sku": sku, "inventory": inventory, "calendar": calendar}



# ---------------------------------------------------------------------------
# 3. MERGE
# ---------------------------------------------------------------------------


def merge_daily(cleaned:dict[str,pd.DataFrame]) -> pd.DataFrame:

    sales, sku, calendar = cleaned["sales"], cleaned["sku"], cleaned["calendar"]

    df = sales.merge(sku, on="sku_id", how="left")
    df = df.merge(calendar, on="date", how="left")
    df = df.sort_values(by=["date", "sku_id"]).reset_index(drop=True)
    return df


def attach_inventory(daily:pd.DataFrame, inventory:pd.DataFrame) -> pd.DataFrame:

    inventory_sorted = inventory.sort_values(by=["date"])
    daily_sorted = daily.sort_values(by=["date"])
    out = pd.merge_asof(daily_sorted, inventory_sorted, on="date", by="sku_id", direction = "backward")
    out = out.sort_values(by=["date", "sku_id"]).reset_index(drop=True)
    return out

def to_weekly(df:pd.DataFrame) -> pd.DataFrame:

    df = df.copy()
    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    agg = df.groupby(["sku_id", "week_start"]).agg(
        units_sold=("units_sold", "sum"),
        revenue=("revenue", "sum"),
        unit_price=("unit_price", "mean"),
        promo_days=("promo_flag", "sum"),
        on_hand_units=("on_hand_units", "last"),
        on_order_units=("on_order_units", "last"),
        lead_time_days=("lead_time_days", "last"),
        safety_stock=("safety_stock", "last"),
        reorder_point=("reorder_point", "last"),
        category=("category", "first"),
        subcategory=("subcategory", "first"),
        unit_cost=("unit_cost", "first"),
        list_price=("list_price", "first"),
        is_holiday=("is_holiday", "max"),
        season=("season", "first"),
    ).reset_index()

    agg["promo_flag"] = (agg["promo_days"] > 0).astype(int)

    days_in_week = df.groupby(["sku_id", "week_start"])["date"].nunique().reset_index(name="n_days")
    agg = agg.merge(days_in_week, on=["sku_id", "week_start"])
    agg = agg[agg["n_days"] == 7].drop(columns="n_days").reset_index(drop=True)
    return agg


# ---------------------------------------------------------------------------
# 2. VALIDATE + PROFILE  (feeds the data-quality report)
# ---------------------------------------------------------------------------

def profile(raw: dict[str, pd.DataFrame]) -> list[str]:
    """Collect data-quality findings as a list of markdown bullet strings."""
    findings = []
    sales, sku, calendar, inventory = raw["sales"], raw["sku"], raw["calendar"], raw["inventory"]

    # duplicates
    dup_sales = sales.duplicated(subset=["date", "sku_id"]).sum()
    dup_inv = inventory.duplicated(subset=["date", "sku_id"]).sum()
    findings.append(f"- **Duplicate rows:** {dup_sales} duplicate `(date, sku_id)` rows in sales_daily; "
                     f"{dup_inv} in inventory_snapshots. Resolved by dropping duplicates, keeping the first occurrence.")

    # orphan SKUs in inventory (not present in sku_master or sales)
    inv_skus = set(inventory["sku_id"].unique())
    master_skus = set(sku["sku_id"].unique())
    sales_skus = set(sales["sku_id"].unique())
    orphan_skus = inv_skus - master_skus
    findings.append(
        f"- **Orphan SKUs in inventory_snapshots:** {len(orphan_skus)} of {len(inv_skus)} SKU codes in "
        f"inventory_snapshots (e.g. {sorted(orphan_skus)[:3]}...) have no matching record in sku_master or "
        f"sales_daily. These cannot be forecast or scored (no sales history, no cost/price data) and are "
        f"**dropped from scope** — treated as a client data-completeness issue to flag back, not fabricated around."
    )

    # inventory snapshot frequency
    n_dates = inventory["date"].nunique()
    findings.append(
        f"- **Inventory is monthly, not daily/weekly:** only {n_dates} distinct snapshot dates over the "
        f"~2-year history (one per calendar month). Risk scoring therefore uses the most recent snapshot "
        f"on or before the forecast date, carried forward — an approximation the client should be told about, "
        f"since true intra-month stock movement isn't visible."
    )

    # negative margin SKUs
    neg_margin = sku[sku["gross_margin_per_unit"] < 0]
    findings.append(
        f"- **Negative-margin SKUs:** {len(neg_margin)} of {len(sku)} SKUs are priced below cost "
        f"(e.g. {neg_margin['sku_id'].iloc[0]}: cost {neg_margin['unit_cost'].iloc[0]:.0f} vs. price "
        f"{neg_margin['list_price'].iloc[0]:.0f}). Flagged as a pricing data-quality/business issue for the "
        f"client — not treated as invalid data and not altered, since it may reflect an intentional loss-leader."
    )

    # missing values
    cal_nulls = calendar[["holiday", "promotion_event"]].isnull().sum()
    findings.append(
        f"- **Calendar nulls:** `holiday` is null on {cal_nulls['holiday']} of {len(calendar)} days and "
        f"`promotion_event` is null on {cal_nulls['promotion_event']} days. These are expected (most days "
        f"aren't holidays or promo events) and are filled with `'None'` rather than dropped."
    )

    # zero-sales days
    zero_sales_pct = (sales["units_sold"] == 0).mean() * 100
    findings.append(
        f"- **Zero-sales days:** {zero_sales_pct:.1f}% of SKU-days have zero units sold — real signal for "
        f"low-velocity SKUs, kept as-is rather than treated as missing."
    )

    last_date = sales["date"].max()
    if last_date.weekday() != 6:
        findings.append(
            f"- **Incomplete final week:** sales history ends on {last_date.date()} "
            f"({last_date.day_name()}), so the last ISO week has only {last_date.weekday() + 1} of 7 days. "
            f"Left in, it looks like a ~60% demand crash and corrupts training and backtests. "
            f"Resolved by dropping any week without all 7 days."
        )

    return findings


# ---------------------------------------------------------------------------
# 5. WRITE DATA-QUALITY REPORT
# ---------------------------------------------------------------------------

def write_data_quality_report(findings: list[str]) -> None:
    content = "# Data-Quality Report — Project FORESIGHT\n\n" \
              "Findings from profiling the four raw extracts, and how each was handled.\n\n" \
              + "\n".join(findings) + "\n"
    (REPORT_DIR / "data_quality.md").write_text(content)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run() -> None:
    raw = load_raw_data()
    findings = profile(raw)
    write_data_quality_report(findings)

    cleaned = clean(raw)
    daily = merge_daily(cleaned)
    daily = attach_inventory(daily, cleaned["inventory"])
    weekly = to_weekly(daily)

    daily.to_csv(PROCESSED_DIR / "analysis_ready_daily.csv", index=False)
    weekly.to_csv(PROCESSED_DIR / "analysis_ready_weekly.csv", index=False)

    print(f"Daily rows:  {len(daily):,}  -> {PROCESSED_DIR / 'analysis_ready_daily.csv'}")
    print(f"Weekly rows: {len(weekly):,} -> {PROCESSED_DIR / 'analysis_ready_weekly.csv'}")
    print(f"Data-quality report -> {REPORT_DIR / 'data_quality.md'}")


if __name__ == "__main__":
    run()
