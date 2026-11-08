"""
routers/kyc.py — KYC document upload, OCR extraction, and validation.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import ConsentLog, KYCSubmission, Lead, Order, get_db
from services import gstin_service, ocr_service, udyam_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kyc", tags=["KYC"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date(2026, 7, 15)
STALE_DAYS = 90  # address proof validity window

VALID_DOC_TYPES = {"gst_cert", "udyam_cert", "signatory_id", "address_proof"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConsentRequest(BaseModel):
    lead_id: int
    consents: dict[str, bool]  # e.g. {"identity_verification": True, "marketing": False}


class ConsentResponse(BaseModel):
    consent_ids: list[int]
    lead_id: int
    consents_recorded: int


class ValidationResult(BaseModel):
    order_id: int
    result: str   # APPROVED / FLAGGED / REJECTED
    issues: list[str]
    checks: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _determine_kyc_result(
    gstin_valid: bool | None,
    udyam_valid: bool | None,
    gstin_status: str | None,
    name_match: bool | None,
    address_valid: bool | None,
    issues: list[str],
) -> str:
    """Determine overall KYC result from individual checks."""
    # REJECTED conditions
    if gstin_status and gstin_status.lower() in ("cancelled", "suspended"):
        return "REJECTED"
    if gstin_valid is False or udyam_valid is False:
        return "REJECTED"
    if address_valid is False:
        return "REJECTED"
    # FLAGGED conditions
    if name_match is False:
        return "FLAGGED"
    if issues:
        return "FLAGGED"
    return "APPROVED"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/consent", response_model=ConsentResponse)
def record_consent(req: ConsentRequest, db: Session = Depends(get_db)) -> ConsentResponse:
    """Record consent choices for a lead."""
    lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {req.lead_id} not found")

    ids: list[int] = []
    for purpose, granted in req.consents.items():
        log = ConsentLog(
            lead_id=req.lead_id,
            purpose=purpose,
            granted=granted,
            granted_at=datetime.utcnow(),
        )
        db.add(log)
        db.flush()
        ids.append(log.id)

    db.commit()
    return ConsentResponse(consent_ids=ids, lead_id=req.lead_id, consents_recorded=len(ids))


@router.post("/upload")
async def upload_document(
    order_id: int = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload a KYC document, run OCR extraction, and validate it.
    Returns extracted fields and a per-document validation result.
    """
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"doc_type must be one of {VALID_DOC_TYPES}",
        )

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    # Save uploaded file
    ext = Path(file.filename or "doc.jpg").suffix or ".jpg"
    unique_name = f"order{order_id}_{doc_type}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = UPLOAD_DIR / unique_name
    content = await file.read()
    save_path.write_bytes(content)

    # OCR extraction
    extracted = ocr_service.extract_from_document(str(save_path), doc_type)

    if "error" in extracted:
        return {
            "order_id": order_id,
            "doc_type": doc_type,
            "file_saved": unique_name,
            "error": extracted["error"],
            "extracted": {},
            "validation": {},
        }

    # Validate extracted data
    validation: dict = {}
    issues: list[str] = []

    if doc_type == "gst_cert":
        gstin = extracted.get("gstin")
        if gstin:
            fmt_ok = gstin_service.validate_gstin_format(gstin)
            registry = gstin_service.lookup_gstin(gstin)
            status = registry["status"] if registry else None
            validation["gstin_format_valid"] = fmt_ok
            validation["gstin_in_registry"] = registry is not None
            validation["gstin_status"] = status
            validation["gstin_active"] = status == "Active" if status else False
            if not fmt_ok:
                issues.append("GSTIN format invalid")
            if not registry:
                issues.append("GSTIN not found in registry")
            elif status != "Active":
                issues.append(f"GSTIN status is {status}")
        else:
            issues.append("No GSTIN extracted from document")
            validation["gstin_in_registry"] = False

    elif doc_type == "udyam_cert":
        udyam_num = extracted.get("udyam_number")
        if udyam_num:
            fmt_ok = udyam_service.validate_udyam_format(udyam_num)
            registry = udyam_service.lookup_udyam(udyam_num)
            validation["udyam_format_valid"] = fmt_ok
            validation["udyam_in_registry"] = registry is not None
            if not fmt_ok:
                issues.append("Udyam number format invalid")
            if not registry:
                issues.append("Udyam number not found in registry")
        else:
            issues.append("No Udyam number extracted from document")
            validation["udyam_in_registry"] = False

    elif doc_type == "address_proof":
        date_valid = extracted.get("date_valid", False)
        validation["date_valid"] = date_valid
        if not date_valid:
            issues.append("Address proof is older than 90 days or date could not be extracted")

    elif doc_type == "signatory_id":
        name = extracted.get("name")
        validation["name_extracted"] = bool(name)
        if not name:
            issues.append("Could not extract signatory name from ID")

    # Update or create KYC submission record
    kyc = db.query(KYCSubmission).filter(KYCSubmission.order_id == order_id).first()
    if not kyc:
        kyc = KYCSubmission(order_id=order_id)
        db.add(kyc)

    if doc_type == "gst_cert":
        kyc.gstin_extracted = extracted.get("gstin")
        kyc.name_extracted = extracted.get("business_name")
        kyc.gstin_valid = validation.get("gstin_active", False)
    elif doc_type == "udyam_cert":
        kyc.udyam_extracted = extracted.get("udyam_number")
        kyc.udyam_valid = validation.get("udyam_in_registry", False)
    elif doc_type == "address_proof":
        kyc.doc_date_extracted = extracted.get("date")
        kyc.address_valid = validation.get("date_valid", False)

    # Merge issues
    existing_issues: list[str] = []
    if kyc.issues:
        try:
            existing_issues = json.loads(kyc.issues)
        except Exception:
            pass
    merged_issues = list(set(existing_issues + issues))
    kyc.issues = json.dumps(merged_issues)
    db.commit()

    return {
        "order_id": order_id,
        "doc_type": doc_type,
        "file_saved": unique_name,
        "extracted": extracted,
        "validation": validation,
        "issues": issues,
    }


@router.get("/{order_id}/status")
def get_kyc_status(order_id: int, db: Session = Depends(get_db)) -> dict:
    """Return full KYC submission status for an order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    kyc = db.query(KYCSubmission).filter(KYCSubmission.order_id == order_id).first()
    if not kyc:
        return {
            "order_id": order_id,
            "kyc_status": order.kyc_status,
            "submission": None,
            "message": "No KYC submission found for this order",
        }

    issues: list[str] = []
    if kyc.issues:
        try:
            issues = json.loads(kyc.issues)
        except Exception:
            issues = [kyc.issues]

    return {
        "order_id": order_id,
        "kyc_status": order.kyc_status,
        "submission": {
            "id": kyc.id,
            "gstin_extracted": kyc.gstin_extracted,
            "udyam_extracted": kyc.udyam_extracted,
            "name_extracted": kyc.name_extracted,
            "address_extracted": kyc.address_extracted,
            "doc_date_extracted": kyc.doc_date_extracted,
            "gstin_valid": kyc.gstin_valid,
            "udyam_valid": kyc.udyam_valid,
            "name_match": kyc.name_match,
            "address_valid": kyc.address_valid,
            "issues": issues,
            "result": kyc.result,
            "created_at": kyc.created_at.isoformat() if kyc.created_at else None,
        },
    }


@router.post("/{order_id}/validate", response_model=ValidationResult)
def validate_kyc(order_id: int, db: Session = Depends(get_db)) -> ValidationResult:
    """
    Run full cross-validation across all uploaded documents for an order:
    - GSTIN vs registry
    - Udyam vs registry
    - GST business name vs Udyam enterprise name (fuzzy match)
    - Address proof date validity
    Then set final KYC result on the order.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    kyc = db.query(KYCSubmission).filter(KYCSubmission.order_id == order_id).first()
    if not kyc:
        raise HTTPException(status_code=404, detail="No KYC submission found — please upload documents first")

    issues: list[str] = []
    checks: dict = {}

    # --- GSTIN validation ---
    gstin_status: str | None = None
    gstin_in_registry = False
    gst_name: str | None = None
    if kyc.gstin_extracted:
        registry = gstin_service.lookup_gstin(kyc.gstin_extracted)
        gstin_in_registry = registry is not None
        checks["gstin_in_registry"] = gstin_in_registry
        if registry:
            gstin_status = registry.get("status")
            gst_name = registry.get("trade_name") or registry.get("legal_name")
            checks["gstin_status"] = gstin_status
            checks["gstin_active"] = gstin_status == "Active"
            if gstin_status != "Active":
                issues.append(f"GSTIN status is {gstin_status} (must be Active)")
        else:
            issues.append("GSTIN not found in registry")
            checks["gstin_status"] = None
    else:
        checks["gstin_in_registry"] = False
        checks["gstin_status"] = None

    # --- Udyam validation ---
    udyam_name: str | None = None
    udyam_in_registry = False
    if kyc.udyam_extracted:
        u_registry = udyam_service.lookup_udyam(kyc.udyam_extracted)
        udyam_in_registry = u_registry is not None
        checks["udyam_in_registry"] = udyam_in_registry
        if u_registry:
            udyam_name = u_registry.get("enterprise_name")
            checks["udyam_enterprise_name"] = udyam_name
        else:
            issues.append("Udyam number not found in registry")
    else:
        checks["udyam_in_registry"] = False

    # --- Cross-check: GST name vs Udyam name ---
    name_match: bool | None = None
    if gst_name and udyam_name:
        name_match = ocr_service.fuzzy_name_match(gst_name, udyam_name, threshold=0.8)
        checks["name_match"] = name_match
        if not name_match:
            issues.append(
                f"Name mismatch: GST says '{gst_name}', Udyam says '{udyam_name}'"
            )
    elif gst_name or udyam_name:
        checks["name_match"] = None  # only one side available

    # --- Address proof date ---
    address_valid: bool | None = kyc.address_valid
    if kyc.doc_date_extracted:
        try:
            doc_date = date.fromisoformat(kyc.doc_date_extracted)
            age_days = (TODAY - doc_date).days
            address_valid = 0 <= age_days <= STALE_DAYS
            checks["address_proof_date"] = kyc.doc_date_extracted
            checks["address_proof_age_days"] = age_days
            checks["address_proof_valid"] = address_valid
            if not address_valid:
                issues.append(f"Address proof is {age_days} days old (max {STALE_DAYS} allowed)")
        except ValueError:
            address_valid = False
            issues.append("Address proof date format could not be parsed")
    else:
        checks["address_proof_valid"] = None

    # --- Determine final result ---
    result = _determine_kyc_result(
        gstin_valid=gstin_in_registry and gstin_status == "Active",
        udyam_valid=udyam_in_registry if kyc.udyam_extracted else None,
        gstin_status=gstin_status,
        name_match=name_match,
        address_valid=address_valid,
        issues=issues,
    )

    # Persist
    kyc.gstin_valid = gstin_in_registry and gstin_status == "Active"
    kyc.udyam_valid = udyam_in_registry if kyc.udyam_extracted else None
    kyc.name_match = name_match
    kyc.address_valid = address_valid
    kyc.issues = json.dumps(issues)
    kyc.result = result

    order.kyc_status = result
    db.commit()

    return ValidationResult(
        order_id=order_id,
        result=result,
        issues=issues,
        checks=checks,
    )
