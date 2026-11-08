"""
routers/leads.py — Back-office lead management and CSV import endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import Lead, get_db
from services import propensity_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["Leads"])

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "Data"
_LEADS_CSV = _DATA_DIR / "smb_leads.csv"

# In-memory cache of scored CSV leads
_csv_leads_cache: list[dict] = []


def _load_csv_leads() -> list[dict]:
    """Load smb_leads.csv with propensity scores merged in."""
    global _csv_leads_cache
    if _csv_leads_cache:
        return _csv_leads_cache

    if not _LEADS_CSV.exists():
        return []

    df = pd.read_csv(_LEADS_CSV, dtype=str).fillna("")
    scores = propensity_model.score_all_leads(_LEADS_CSV)

    records = df.to_dict("records")
    for rec in records:
        lid = str(rec.get("lead_id", ""))
        rec["propensity_score"] = scores.get(lid, 50.0)
        rec["score_tier"] = propensity_model.get_score_tier(rec["propensity_score"])

    _csv_leads_cache = records
    return records


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_lead_stats() -> dict:
    """Return summary statistics across all leads from the CSV."""
    leads = _load_csv_leads()
    if not leads:
        return {"error": "No leads data available"}

    total = len(leads)
    activated = sum(1 for l in leads if str(l.get("outcome", "")).strip() == "Activated")
    conversion_rate = round(activated / total * 100, 2) if total else 0.0

    # Avg score by segment
    from collections import defaultdict
    seg_scores: dict[str, list[float]] = defaultdict(list)
    for l in leads:
        seg = str(l.get("segment", "Unknown")).strip()
        seg_scores[seg].append(float(l.get("propensity_score", 50)))
    avg_score_by_segment = {seg: round(sum(scores) / len(scores), 2) for seg, scores in seg_scores.items()}

    # Top drop reasons
    drop_reasons: dict[str, int] = {}
    for l in leads:
        reason = str(l.get("drop_reason", "")).strip()
        if reason:
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
    top_drop_reasons = sorted(drop_reasons.items(), key=lambda x: -x[1])[:10]

    # Leads by outcome
    outcomes: dict[str, int] = {}
    for l in leads:
        o = str(l.get("outcome", "Unknown")).strip()
        outcomes[o] = outcomes.get(o, 0) + 1

    return {
        "total_leads": total,
        "activated": activated,
        "conversion_rate_pct": conversion_rate,
        "avg_score_by_segment": avg_score_by_segment,
        "top_drop_reasons": [{"reason": r, "count": c} for r, c in top_drop_reasons],
        "leads_by_outcome": outcomes,
    }


@router.post("/import")
def import_leads_from_csv(db: Session = Depends(get_db)) -> dict:
    """
    Seed the database with leads from smb_leads.csv.
    Skips already-imported leads (by session_id == lead_id).
    """
    if not _LEADS_CSV.exists():
        raise HTTPException(status_code=404, detail="smb_leads.csv not found")

    df = pd.read_csv(_LEADS_CSV, dtype=str).fillna("")
    scores = propensity_model.score_all_leads(_LEADS_CSV)

    imported = 0
    skipped = 0
    for _, row in df.iterrows():
        lid = str(row.get("lead_id", "")).strip()
        if not lid:
            continue
        # Check if already imported
        existing = db.query(Lead).filter(Lead.session_id == f"csv:{lid}").first()
        if existing:
            skipped += 1
            continue

        has_gstin = str(row.get("has_gstin", "N")).strip().upper() in ("Y", "YES", "TRUE")
        has_udyam = str(row.get("has_udyam", "N")).strip().upper() in ("Y", "YES", "TRUE")

        try:
            city_tier = int(row.get("city_tier", 2))
        except ValueError:
            city_tier = 2
        try:
            emp_count = int(row.get("employee_count", 1))
        except ValueError:
            emp_count = 1
        try:
            num_sites = int(row.get("num_sites", 1))
        except ValueError:
            num_sites = 1
        try:
            monthly_spend = float(row.get("monthly_telecom_spend_inr", 0))
        except ValueError:
            monthly_spend = 0.0

        lead = Lead(
            session_id=f"csv:{lid}",
            business_name=str(row.get("business_name", "")).strip(),
            business_type=str(row.get("business_type", "")).strip(),
            segment=str(row.get("segment", "")).strip(),
            city=str(row.get("city", "")).strip(),
            city_tier=city_tier,
            state=str(row.get("state", "")).strip(),
            language=str(row.get("preferred_language", "")).strip(),
            employee_count=emp_count,
            num_sites=num_sites,
            has_gstin=has_gstin,
            gstin=str(row.get("gstin", "")).strip() or None,
            has_udyam=has_udyam,
            udyam_number=str(row.get("udyam_number", "")).strip() or None,
            monthly_spend=monthly_spend,
            products_of_interest=str(row.get("products_of_interest", "")).strip(),
            contact_name=str(row.get("contact_name", "")).strip(),
            contact_role=str(row.get("contact_role", "")).strip(),
            stage_reached=str(row.get("stage_reached", "Lead")).strip(),
            outcome=str(row.get("outcome", "In Progress")).strip(),
            drop_reason=str(row.get("drop_reason", "")).strip() or None,
            propensity_score=scores.get(lid, 50.0),
        )
        db.add(lead)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "total_in_csv": len(df)}


@router.get("")
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    outcome: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    city_tier: Optional[int] = Query(None),
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    drop_reason: Optional[str] = Query(None),
    source: str = Query("csv", description="csv or db"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Paginated lead list with optional filters.
    source=csv reads from smb_leads.csv; source=db reads from SQLite.
    """
    if source == "csv":
        leads = _load_csv_leads()

        # Apply filters
        if outcome:
            leads = [l for l in leads if str(l.get("outcome", "")).lower() == outcome.lower()]
        if segment:
            leads = [l for l in leads if str(l.get("segment", "")).lower() == segment.lower()]
        if city_tier is not None:
            leads = [l for l in leads if str(l.get("city_tier", "")).strip() == str(city_tier)]
        if min_score is not None:
            leads = [l for l in leads if float(l.get("propensity_score", 0)) >= min_score]
        if max_score is not None:
            leads = [l for l in leads if float(l.get("propensity_score", 100)) <= max_score]
        if drop_reason:
            leads = [l for l in leads if drop_reason.lower() in str(l.get("drop_reason", "")).lower()]

        total = len(leads)
        start = (page - 1) * page_size
        paginated = leads[start : start + page_size]
        return {"leads": paginated, "total": total, "page": page, "page_size": page_size, "source": "csv"}

    else:
        query = db.query(Lead)
        if outcome:
            query = query.filter(Lead.outcome == outcome)
        if segment:
            query = query.filter(Lead.segment == segment)
        if city_tier is not None:
            query = query.filter(Lead.city_tier == city_tier)
        if min_score is not None:
            query = query.filter(Lead.propensity_score >= min_score)
        if max_score is not None:
            query = query.filter(Lead.propensity_score <= max_score)
        if drop_reason:
            query = query.filter(Lead.drop_reason.like(f"%{drop_reason}%"))

        total = query.count()
        db_leads = query.offset((page - 1) * page_size).limit(page_size).all()

        def _lead_to_dict(l: Lead) -> dict:
            return {
                "id": l.id,
                "session_id": l.session_id,
                "business_name": l.business_name,
                "segment": l.segment,
                "city": l.city,
                "city_tier": l.city_tier,
                "state": l.state,
                "outcome": l.outcome,
                "stage_reached": l.stage_reached,
                "propensity_score": l.propensity_score,
                "score_tier": propensity_model.get_score_tier(l.propensity_score or 50),
                "drop_reason": l.drop_reason,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }

        return {
            "leads": [_lead_to_dict(l) for l in db_leads],
            "total": total,
            "page": page,
            "page_size": page_size,
            "source": "db",
        }


@router.get("/{lead_id}")
def get_lead(lead_id: str, source: str = Query("csv"), db: Session = Depends(get_db)) -> dict:
    """Return a single lead by lead_id (CSV format like 'L00001') or DB integer id."""
    if source == "csv":
        leads = _load_csv_leads()
        # Try direct match on lead_id column
        matched = [l for l in leads if str(l.get("lead_id", "")) == lead_id]
        if not matched:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found in CSV")
        return matched[0]

    # DB lookup
    try:
        lid = int(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="For DB source, lead_id must be an integer")

    lead = db.query(Lead).filter(Lead.id == lid).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found in database")

    return {
        "id": lead.id,
        "session_id": lead.session_id,
        "business_name": lead.business_name,
        "business_type": lead.business_type,
        "segment": lead.segment,
        "city": lead.city,
        "city_tier": lead.city_tier,
        "state": lead.state,
        "language": lead.language,
        "employee_count": lead.employee_count,
        "num_sites": lead.num_sites,
        "has_gstin": lead.has_gstin,
        "gstin": lead.gstin,
        "has_udyam": lead.has_udyam,
        "udyam_number": lead.udyam_number,
        "monthly_spend": lead.monthly_spend,
        "products_of_interest": lead.products_of_interest,
        "contact_name": lead.contact_name,
        "contact_role": lead.contact_role,
        "stage_reached": lead.stage_reached,
        "outcome": lead.outcome,
        "drop_reason": lead.drop_reason,
        "propensity_score": lead.propensity_score,
        "score_tier": propensity_model.get_score_tier(lead.propensity_score or 50),
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }
