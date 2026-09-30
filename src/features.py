"""
Project FORESIGHT — Feature Engineering
=========================================
Builds leakage-free weekly features for the demand forecast model.
Every feature at week t uses only data available up to and including week t-1
(lags/rolling stats) or is known in advance (calendar).
"""
import pandas as pd
import numpy as np


def build_features(weekly: pd.DataFrame) -> pd.DataFrame:
    df = weekly.sort_values(["sku_id", "week_start"]).copy()
    g = df.groupby("sku_id")["units_sold"]

    # --- lag features (strictly past values) ---
    for lag in [1, 2, 4, 8, 52]:
        df[f"lag_{lag}"] = g.shift(lag)

    # --- rolling statistics computed on shifted series (no current-week leakage) ---
    shifted = g.shift(1)
    df["roll_mean_4"] = shifted.groupby(df["sku_id"]).transform(lambda s: s.rolling(4, min_periods=1).mean())
    df["roll_mean_8"] = shifted.groupby(df["sku_id"]).transform(lambda s: s.rolling(8, min_periods=1).mean())
    df["roll_std_4"] = shifted.groupby(df["sku_id"]).transform(lambda s: s.rolling(4, min_periods=1).std())

    # --- calendar features (known in advance, safe) ---
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["month"] = df["week_start"].dt.month
    df["weekofyear"] = df["week_start"].dt.isocalendar().week.astype(int)
    df["season"] = df["season"].astype("category")
    df["category"] = df["category"].astype("category")

    # --- promo: only the current week's *scheduled* promo flag is used, which is
    #     legitimate because promo calendars are planned in advance by the business ---
    # (kept as promo_flag, already in weekly df)

    # --- recent promo intensity (past exposure, safe) ---
    promo_shifted = df.groupby("sku_id")["promo_flag"].shift(1)
    df["recent_promo_rate_4"] = promo_shifted.groupby(df["sku_id"]).transform(
        lambda s: s.rolling(4, min_periods=1).mean()
    )

    return df


FEATURE_COLS = [
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_52",
    "roll_mean_4", "roll_mean_8", "roll_std_4",
    "month", "weekofyear", "is_holiday", "promo_flag", "recent_promo_rate_4",
    "category", "season",
]
TARGET_COL = "units_sold"
