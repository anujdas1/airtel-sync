"""
routers/scoring.py — Machine Learning Propensity Scoring API.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from services import propensity_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/score", tags=["Scoring"])

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "Data"
_LEADS_CSV = _DATA_DIR / "smb_leads.csv"


class BatchScoreRequest(BaseModel):
    lead_ids: List[str]


class LeadPredictionRequest(BaseModel):
    segment: str = "Micro retail & services"
    has_gstin: str = "Y"
    has_udyam: str = "N"
    city_tier: int = 2
    employee_count: int = 5
    num_sites: int = 1
    monthly_telecom_spend_inr: float = 3000.0
    lead_source: str = "Website form"
    products_of_interest: str = "P01;P07"
    stage_reached: str = "Needs assessed"


@router.get("/features")
def get_features():
    """Return top feature importances from the trained ML propensity model."""
    importances = propensity_model.get_feature_importances()
    return {
        "features": importances,
        "model_type": "RandomForestClassifier",
        "n_estimators": 100,
        "status": "trained",
    }


@router.get("/{lead_id}")
def get_lead_score(lead_id: str):
    """Get propensity score for a specific synthetic lead ID."""
    scores = propensity_model.score_all_leads(_LEADS_CSV)
    if lead_id not in scores:
        raise HTTPException(status_code=404, detail=f"Lead ID '{lead_id}' not found in registry")
    
    score = scores[lead_id]
    tier = propensity_model.get_score_tier(score)
    
    # Recommendation logic
    if tier == "Hot":
        action = "Call immediately within 2 hours. High closing probability."
    elif tier == "Warm":
        action = "Send WhatsApp bundle quote with 1-click checkout link."
    else:
        action = "Nurture with automated email and SMS product catalogue."

    return {
        "lead_id": lead_id,
        "propensity_score": score,
        "score_tier": tier,
        "recommended_action": action,
    }


@router.post("/batch")
def score_batch(req: BatchScoreRequest):
    """Score multiple leads in a batch."""
    scores = propensity_model.score_all_leads(_LEADS_CSV)
    results = []
    for lid in req.lead_ids:
        score = scores.get(lid, 50.0)
        results.append({
            "lead_id": lid,
            "propensity_score": score,
            "score_tier": propensity_model.get_score_tier(score)
        })
    return {"results": results, "count": len(results)}


@router.post("/predict")
def predict_propensity(req: LeadPredictionRequest):
    """Predict propensity score for any live lead attributes."""
    score = propensity_model.score_lead(req.dict())
    tier = propensity_model.get_score_tier(score)
    return {
        "propensity_score": score,
        "score_tier": tier,
        "inputs": req.dict()
    }

