"""
services/propensity_model.py — Random Forest propensity scorer for MSME leads.

Trained on smb_leads.csv.  Target: outcome == "Activated" → 1, else 0.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_model: Optional[RandomForestClassifier] = None
_feature_names: list[str] = []
_all_scores: dict[str, float] = {}   # lead_id → score (0–100)

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------
_SEGMENT_MAP = {
    "Micro retail & services": 0,
    "micro": 0,
    "Professional offices": 1,
    "prof": 1,
    "Small multi-site businesses": 2,
    "multi": 2,
    "Small manufacturers": 3,
    "mfg": 3,
}

_STAGE_MAP = {
    "Lead": 0,
    "Contacted": 1,
    "Needs assessed": 2,
    "Quote accepted": 3,
    "KYC complete": 4,
    "Activated": 5,
}

_SOURCE_COLS = [
    "source_field_sales",
    "source_website_form",
    "source_channel_partner",
    "source_inbound_call",
    "source_referral",
    "source_whatsapp_campaign",
]


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a numeric feature matrix from raw leads dataframe."""
    feat = pd.DataFrame()

    # Segment (ordinal)
    feat["segment"] = df["segment"].map(
        lambda s: _SEGMENT_MAP.get(s, _SEGMENT_MAP.get(str(s).strip(), 0))
    ).fillna(0).astype(int)

    # Binary flags
    feat["has_gstin"] = (
        df["has_gstin"].astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])
    ).astype(int)
    feat["has_udyam"] = (
        df["has_udyam"].astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])
    ).astype(int)

    # City tier
    feat["city_tier"] = pd.to_numeric(df.get("city_tier", pd.Series([2] * len(df))), errors="coerce").fillna(2).astype(int)

    # Employee count
    feat["employee_count"] = pd.to_numeric(df.get("employee_count", pd.Series([1] * len(df))), errors="coerce").fillna(1)

    # Number of sites
    feat["num_sites"] = pd.to_numeric(df.get("num_sites", pd.Series([1] * len(df))), errors="coerce").fillna(1)

    # Monthly spend (normalised 0–1 based on max 50 000)
    spend = pd.to_numeric(df.get("monthly_telecom_spend_inr", pd.Series([0] * len(df))), errors="coerce").fillna(0)
    feat["monthly_spend_norm"] = (spend / 50_000).clip(0, 1)

    # Products of interest count
    poi = df.get("products_of_interest", pd.Series([""] * len(df))).fillna("")
    feat["products_of_interest_count"] = poi.apply(
        lambda x: len([p for p in str(x).split(";") if p.strip()])
    )

    # Stage reached (ordinal)
    feat["stage_reached"] = df.get("stage_reached", pd.Series(["Lead"] * len(df))).map(
        lambda s: _STAGE_MAP.get(str(s).strip(), 0)
    ).fillna(0).astype(int)

    # Lead source (one-hot)
    source_col = df.get("lead_source", pd.Series([""] * len(df))).fillna("")
    for col_name, source_val in [
        ("source_field_sales", "Field sales"),
        ("source_website_form", "Website form"),
        ("source_channel_partner", "Channel partner"),
        ("source_inbound_call", "Inbound call"),
        ("source_referral", "Referral"),
        ("source_whatsapp_campaign", "WhatsApp campaign"),
    ]:
        feat[col_name] = (source_col == source_val).astype(int)

    return feat


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_model(csv_path: str | Path) -> dict:
    """Train the RandomForest on smb_leads.csv and cache all lead scores. Returns metrics dict."""
    global _model, _feature_names, _all_scores

    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error("CSV not found: %s", csv_path)
        return

    df = pd.read_csv(csv_path, dtype=str).fillna("")

    # Build target
    y = (df["outcome"].str.strip() == "Activated").astype(int)

    # Build features
    X = _build_features(df)
    _feature_names = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X.values, y.values, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    # Evaluation
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_test, y_prob)
    except Exception:
        auc = float("nan")

    logger.info(
        "Propensity model trained — Acc: %.3f  Prec: %.3f  Rec: %.3f  AUC: %.3f",
        acc, prec, rec, auc,
    )
    print(
        f"[PropensityModel] Accuracy={acc:.3f}  Precision={prec:.3f}  "
        f"Recall={rec:.3f}  AUC={auc:.3f}"
    )

    _model = clf

    # Score all leads
    all_probs = clf.predict_proba(X.values)[:, 1]
    lead_ids = df["lead_id"].tolist()
    _all_scores = {lid: round(float(p) * 100, 2) for lid, p in zip(lead_ids, all_probs)}

    return {"accuracy": round(float(acc), 3), "precision": round(float(prec), 3), "recall": round(float(rec), 3), "auc": round(float(auc), 3)}


# ---------------------------------------------------------------------------
# Scoring API
# ---------------------------------------------------------------------------

def score_lead(lead_dict: dict) -> float:
    """Score a single lead dict (with same field names as the CSV). Returns 0–100."""
    if _model is None:
        return 50.0
    row = pd.DataFrame([lead_dict])
    X = _build_features(row)
    # Align columns
    for col in _feature_names:
        if col not in X.columns:
            X[col] = 0
    X = X[_feature_names]
    prob = _model.predict_proba(X.values)[0][1]
    return round(float(prob) * 100, 2)


def score_all_leads(csv_path: str | Path) -> dict[str, float]:
    """Return cached {lead_id: score} dict (populated during train_model)."""
    if _all_scores:
        return _all_scores
    # Fallback: re-train if cache is empty
    train_model(csv_path)
    return _all_scores


def get_feature_importances() -> dict[str, float]:
    """Return {feature_name: importance} from trained model."""
    if _model is None or not _feature_names:
        return {}
    importances = _model.feature_importances_
    return {name: round(float(imp), 6) for name, imp in zip(_feature_names, importances)}


def get_score_tier(score: float) -> str:
    """Classify a 0–100 score into Hot / Warm / Cold."""
    if score > 70:
        return "Hot"
    if score >= 30:
        return "Warm"
    return "Cold"
