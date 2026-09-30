"""
Project FORESIGHT — Scoring Service (FastAPI)
================================================
Run:
    uvicorn service.main:app --reload --port 8000

Endpoints:
    GET  /                     health check
    GET  /skus                 list of scoreable SKU ids
    GET  /forecast/{sku_id}    forecast for one SKU over the horizon
    GET  /risk/{sku_id}        risk score + recommended action for one SKU
    POST /score/batch          forecast + risk for a list of SKU ids
"""
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

app = FastAPI(
    title="Project FORESIGHT Scoring Service",
    description="Returns demand forecast and stockout/overstock risk for NorthBay Living SKUs.",
    version="1.0.0",
)

_forecast_df: Optional[pd.DataFrame] = None
_risk_df: Optional[pd.DataFrame] = None


def _load():
    global _forecast_df, _risk_df
    if _forecast_df is None or _risk_df is None:
        try:
            _forecast_df = pd.read_csv(PROC_DIR / "forecast_latest.csv", parse_dates=["horizon_week"])
            _risk_df = pd.read_csv(PROC_DIR / "risk_scores.csv")
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=f"Model outputs not found — run the pipeline first: {e}")
    return _forecast_df, _risk_df


class BatchRequest(BaseModel):
    sku_ids: List[str]


@app.get("/")
def health():
    return {"status": "ok", "service": "Project FORESIGHT scoring service"}


@app.get("/skus")
def list_skus():
    _, risk_df = _load()
    return {"skus": sorted(risk_df["sku_id"].unique().tolist())}


@app.get("/forecast/{sku_id}")
def get_forecast(sku_id: str):
    forecast_df, _ = _load()
    sub = forecast_df[forecast_df["sku_id"] == sku_id.upper()]
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"No forecast found for SKU '{sku_id}'. "
                                                      f"Check the SKU id (e.g. SKU001) and try again.")
    return {
        "sku_id": sku_id.upper(),
        "forecast": [
            {
                "week": row["horizon_week"].strftime("%Y-%m-%d"),
                "forecast_units": round(float(row["forecast_units"]), 1),
                "low": round(float(row["forecast_low"]), 1),
                "high": round(float(row["forecast_high"]), 1),
            }
            for _, row in sub.sort_values("horizon_week").iterrows()
        ],
    }


@app.get("/risk/{sku_id}")
def get_risk(sku_id: str):
    _, risk_df = _load()
    sub = risk_df[risk_df["sku_id"] == sku_id.upper()]
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"No risk score found for SKU '{sku_id}'. "
                                                      f"Check the SKU id (e.g. SKU001) and try again.")
    r = sub.iloc[0]
    return {
        "sku_id": sku_id.upper(),
        "risk_quadrant": r["risk_quadrant"],
        "stockout_risk": round(float(r["stockout_risk"]), 3),
        "overstock_risk": round(float(r["overstock_risk"]), 3),
        "recommended_action": r["recommended_action"],
        "rupees_at_stake": round(float(r["rupees_at_stake"]), 2),
    }


@app.post("/score/batch")
def score_batch(req: BatchRequest):
    if not req.sku_ids:
        raise HTTPException(status_code=400, detail="sku_ids must be a non-empty list.")
    results = []
    for sku_id in req.sku_ids:
        try:
            forecast = get_forecast(sku_id)
            risk = get_risk(sku_id)
            results.append({"sku_id": sku_id.upper(), "forecast": forecast["forecast"], "risk": risk})
        except HTTPException as e:
            results.append({"sku_id": sku_id.upper(), "error": e.detail})
    return {"results": results}
