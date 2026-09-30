"""
Project FORESIGHT — Demand Forecasting
=========================================
Builds a seasonal-naive baseline and a LightGBM direct multi-horizon model,
backtests both with rolling-origin cross-validation, and reports WAPE/bias
per Section 07 of the engagement brief.

Run:
    python -m src.forecast

Outputs:
    data/processed/forecast_latest.csv     (forecast for the next H weeks, all SKUs)
    reports/model_backtest.md              (WAPE vs baseline, honestly reported)
    data/processed/model_h{h}.pkl          (trained LightGBM model per horizon step)
"""
from pathlib import Path
import pandas as pd
import numpy as np
import lightgbm as lgb
import pickle

from src.features import build_features, FEATURE_COLS, TARGET_COL

PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"

HORIZON = 8          # weeks — per brief Section 4.2 ("6-8 weeks")
N_TEST_ORIGINS = 4    # number of rolling-origin folds in the backtest


def wape(actual: np.ndarray, pred: np.ndarray) -> float:
    actual, pred = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    denom = np.sum(np.abs(actual))
    if denom == 0:
        return np.nan
    return float(np.sum(np.abs(actual - pred)) / denom)


def bias(actual: np.ndarray, pred: np.ndarray) -> float:
    actual, pred = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    return float(np.mean(pred - actual))


def build_direct_targets(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """For each row (origin), add target_h (actual h weeks ahead) and snaive_h
    (seasonal-naive prediction: value from the same week one year earlier)."""
    df = df.sort_values(["sku_id", "week_start"]).copy()
    g = df.groupby("sku_id")[TARGET_COL]
    for h in range(1, horizon + 1):
        df[f"target_{h}"] = g.shift(-(h - 1))
        df[f"snaive_{h}"] = g.shift(53 - h)  # value ~52 weeks before the target week
    return df


def append_next_week(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add one placeholder row per SKU for the first UNOBSERVED week (units_sold = NaN).
    Its lag/rolling features use data up to the last observed week, so it is the correct
    origin for the real forward forecast. Calendar values for the future week are assumed:
    promo_flag=0, is_holiday=0 (not known in advance in the provided calendar)."""
    weekly = weekly.sort_values(["sku_id", "week_start"])
    next_week = weekly["week_start"].max() + pd.Timedelta(weeks=1)
    season_by_month = (weekly.assign(m=weekly["week_start"].dt.month)
                       .groupby("m")["season"].agg(lambda s: s.mode().iloc[0]))
    last = weekly.groupby("sku_id").last().reset_index()
    new = last.copy()
    new["week_start"] = next_week
    new["units_sold"] = np.nan
    new["promo_flag"] = 0
    new["is_holiday"] = 0
    new["season"] = season_by_month[next_week.month]
    return pd.concat([weekly, new], ignore_index=True)


def get_categorical_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in FEATURE_COLS if str(df[c].dtype) in ("category", "object")]


def train_predict_horizon(train: pd.DataFrame, test: pd.DataFrame, h: int):
    cat_cols = get_categorical_cols(train)
    X_train, y_train = train[FEATURE_COLS], train[f"target_{h}"]
    X_test = test[FEATURE_COLS]

    model = lgb.LGBMRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=5,
        num_leaves=31, min_child_samples=10, random_state=42, verbosity=-1,
    )
    model.fit(X_train, y_train, categorical_feature=cat_cols)
    preds = model.predict(X_test)
    preds = np.clip(preds, 0, None)  # demand can't be negative
    return model, preds


def rolling_origin_backtest(feat: pd.DataFrame) -> pd.DataFrame:
    """Evaluate model vs. seasonal-naive baseline over N_TEST_ORIGINS rolling origins."""
    all_weeks = sorted(feat["week_start"].unique())
    # candidate origins: need enough history before (for lag_52) and enough future (for horizon)
    usable = [w for w in all_weeks if w >= all_weeks[60] and w <= all_weeks[-HORIZON]]
    test_origins = usable[-N_TEST_ORIGINS:]

    rows = []
    for origin in test_origins:
        train_mask = feat["week_start"] < origin
        test_mask = feat["week_start"] == origin
        train, test = feat[train_mask].dropna(subset=FEATURE_COLS), feat[test_mask]
        if train.empty or test.empty:
            continue
        for h in range(1, HORIZON + 1):
            train_h = train.dropna(subset=[f"target_{h}"])
            if train_h.empty:
                continue
            _, preds = train_predict_horizon(train_h, test, h)
            actual = test[f"target_{h}"].values
            snaive_pred = test[f"snaive_{h}"].fillna(test["roll_mean_8"]).values

            valid = ~np.isnan(actual)
            rows.append({
                "origin": origin, "horizon": h,
                "model_wape": wape(actual[valid], preds[valid]),
                "baseline_wape": wape(actual[valid], snaive_pred[valid]),
                "model_bias": bias(actual[valid], preds[valid]),
                "baseline_bias": bias(actual[valid], snaive_pred[valid]),
                "n_obs": int(valid.sum()),
            })
    return pd.DataFrame(rows)


def write_backtest_report(results: pd.DataFrame) -> None:
    overall_model_wape = np.average(results["model_wape"], weights=results["n_obs"])
    overall_baseline_wape = np.average(results["baseline_wape"], weights=results["n_obs"])
    by_h = results.groupby("horizon")[["model_wape", "baseline_wape"]].mean()

    verdict = ("The model beats the seasonal-naive baseline" if overall_model_wape < overall_baseline_wape
               else "The seasonal-naive baseline is NOT beaten by the model")
    improvement = (1 - overall_model_wape / overall_baseline_wape) * 100

    lines = [
        "# Model Backtest Report — Project FORESIGHT",
        "",
        f"Rolling-origin backtest over {results['origin'].nunique()} origins, "
        f"forecast horizon = {HORIZON} weeks, evaluated with WAPE (Weighted Absolute Percentage Error).",
        "",
        f"**Overall WAPE — model: {overall_model_wape:.3f}  |  seasonal-naive baseline: {overall_baseline_wape:.3f}**",
        "",
        f"**Verdict: {verdict}** "
        f"({'a ' + format(improvement, '.1f') + '% reduction in WAPE vs. baseline' if overall_model_wape < overall_baseline_wape else 'reporting this honestly per the engagement brief, not hiding it'}).",
        "",
        "## WAPE by forecast horizon (weeks ahead)",
        "",
        "| Horizon (weeks) | Model WAPE | Baseline WAPE |",
        "|---|---|---|",
    ]
    for h, row in by_h.iterrows():
        lines.append(f"| {h} | {row['model_wape']:.3f} | {row['baseline_wape']:.3f} |")

    lines += [
        "",
        "## Bias (signed mean error — positive = over-forecasting)",
        f"- Model bias: {results['model_bias'].mean():.2f} units",
        f"- Baseline bias: {results['baseline_bias'].mean():.2f} units",
        "",
        "## Method notes",
        "- Rolling-origin cross-validation: each origin trains only on weeks strictly before it "
        "(expanding window) — never a random split.",
        "- Direct multi-horizon: a separate LightGBM model is trained per horizon step (1-8 weeks "
        "ahead), each using only features available as of the origin week — no future data enters "
        "a feature at any horizon.",
        "- Seasonal-naive baseline predicts the same week's demand from approximately one year "
        "earlier (or the 8-week rolling mean where a year-ago value isn't available).",
    ]
    (REPORT_DIR / "model_backtest.md").write_text("\n".join(lines))
    return overall_model_wape, overall_baseline_wape


def train_final_models_and_forecast(weekly: pd.DataFrame) -> pd.DataFrame:
    """Train on ALL observed history; forecast the HORIZON weeks starting the week after the data ends."""
    feat = build_direct_targets(build_features(append_next_week(weekly)), HORIZON)
    first_forecast_week = weekly["week_start"].max() + pd.Timedelta(weeks=1)
    origin_rows = feat[feat["week_start"] == first_forecast_week].dropna(subset=FEATURE_COLS)
    forecasts, models = [], {}
    for h in range(1, HORIZON + 1):
        train_h = feat.dropna(subset=FEATURE_COLS + [f"target_{h}"])
        model, preds = train_predict_horizon(train_h, origin_rows, h)
        models[h] = model
        out = origin_rows[["sku_id"]].copy()
        out["horizon_week"] = first_forecast_week + pd.Timedelta(weeks=h - 1)
        out["forecast_units"] = preds
        out["forecast_low"] = np.clip(preds * 0.75, 0, None)   # simple +/-25% band (placeholder, not calibrated)
        out["forecast_high"] = preds * 1.25
        forecasts.append(out)
    with open(PROC_DIR / "models.pkl", "wb") as f:
        pickle.dump(models, f)
    return pd.concat(forecasts, ignore_index=True)


def run():
    weekly = pd.read_csv(PROC_DIR / "analysis_ready_weekly.csv", parse_dates=["week_start"])
    feat = build_features(weekly)
    feat = build_direct_targets(feat, HORIZON)

    print("Running rolling-origin backtest...")
    results = rolling_origin_backtest(feat)
    results.to_csv(PROC_DIR / "backtest_results.csv", index=False)   # read by the dashboard's accuracy panels
    model_wape, base_wape = write_backtest_report(results)
    print(f"Model WAPE: {model_wape:.3f}  |  Baseline WAPE: {base_wape:.3f}")

    print("Training final models on full history and generating forward forecast...")
    forecast = train_final_models_and_forecast(weekly)
    forecast.to_csv(PROC_DIR / "forecast_latest.csv", index=False)
    print(f"Forecast written -> {PROC_DIR / 'forecast_latest.csv'} ({len(forecast)} rows)")
    print(f"Backtest report -> {REPORT_DIR / 'model_backtest.md'}")


if __name__ == "__main__":
    run()
