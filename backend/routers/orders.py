"""
routers/orders.py — Order creation and tracking for Accel SYNC.
"""
from __future__ import annotations

import json
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Order, Lead, get_db
from routers.catalogue import get_catalogue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["Orders"])

# ---------------------------------------------------------------------------
# Order status stages (in sequence)
# ---------------------------------------------------------------------------
ORDER_STAGES = [
    "Order Placed",
    "KYC Verified",
    "Order Processing",
    "Field Tech Scheduled",
    "Installation Complete",
    "Service Activated",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_order_ref() -> str:
    """Generate a unique order reference like ACC-2026-XXXXX."""
    suffix = "".join(random.choices(string.ascii_uppercase, k=5))
    return f"ACC-2026-{suffix}"


def _get_max_install_days(product_ids: list[str]) -> int:
    """Return the maximum typical_install_days from the given product IDs."""
    df = get_catalogue()
    max_days = 0
    for pid in product_ids:
        row = df[df["product_id"] == pid.upper()]
        if not row.empty:
            days = int(row.iloc[0]["typical_install_days"])
            max_days = max(max_days, days)
    return max(max_days, 1)


def _build_timeline(status: str, created_at: datetime, install_date: datetime | None) -> list[dict]:
    """
    Build an ordered timeline list for the order status.
    Each entry: {stage, status: completed|current|upcoming, date}
    """
    current_idx = ORDER_STAGES.index(status) if status in ORDER_STAGES else 0
    timeline = []
    for i, stage in enumerate(ORDER_STAGES):
        if i < current_idx:
            # Estimate past dates proportionally
            if install_date and i > 0:
                total_seconds = (install_date - created_at).total_seconds()
                step = total_seconds / max(len(ORDER_STAGES) - 1, 1)
                est = created_at + timedelta(seconds=step * i)
            else:
                est = created_at + timedelta(days=i)
            timeline.append({"stage": stage, "status": "completed", "date": est.isoformat()})
        elif i == current_idx:
            timeline.append({"stage": stage, "status": "current", "date": datetime.utcnow().isoformat()})
        else:
            timeline.append({"stage": stage, "status": "upcoming", "date": None})
    return timeline


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class BundleProduct(BaseModel):
    product_id: str
    quantity: int = 1


class CreateOrderRequest(BaseModel):
    lead_id: Optional[int] = None
    bundle_products: Optional[list[BundleProduct]] = None
    product_ids: Optional[list[str]] = None
    contract_months: int = 12


class UpdateStatusRequest(BaseModel):
    status: Optional[str] = None  # if None, cycle to next stage


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("")
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)) -> dict:
    """Create a new order from a bundle of products."""
    products = req.bundle_products or []
    if not products and req.product_ids:
        products = [BundleProduct(product_id=pid) for pid in req.product_ids]

    if not products:
        raise HTTPException(status_code=400, detail="bundle_products or product_ids cannot be empty")

    # Validate products exist
    df = get_catalogue()
    monthly_total = 0.0
    setup_fee = 0.0
    product_ids: list[str] = []

    for bp in products:
        pid = bp.product_id.upper()
        row = df[df["product_id"] == pid]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"Product {pid} not found")
        r = row.iloc[0]
        price = float(r["price_min_inr_per_month"]) * bp.quantity
        setup = float(r["one_time_setup_inr"])
        monthly_total += price
        setup_fee += setup
        product_ids.append(pid)

    # Validate lead if provided
    if req.lead_id:
        lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {req.lead_id} not found")

    # Build order ref (ensure uniqueness)
    for _ in range(10):
        ref = _generate_order_ref()
        existing = db.query(Order).filter(Order.order_ref == ref).first()
        if not existing:
            break

    max_install_days = _get_max_install_days(product_ids)
    est_activation = datetime.utcnow() + timedelta(days=max_install_days)

    bundle_json = json.dumps([{"product_id": bp.product_id.upper(), "quantity": bp.quantity} for bp in products])

    order = Order(
        lead_id=req.lead_id,
        order_ref=ref,
        bundle_products=bundle_json,
        monthly_total=round(monthly_total, 2),
        setup_fee=round(setup_fee, 2),
        contract_months=req.contract_months,
        status="Order Placed",
        kyc_status="Pending",
        estimated_activation_date=est_activation,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "order_ref": order.order_ref,
        "id": order.id,
        "order_id": order.id,
        "lead_id": order.lead_id,
        "bundle_products": products,
        "monthly_total": order.monthly_total,
        "setup_fee": order.setup_fee,
        "contract_months": order.contract_months,
        "status": order.status,
        "kyc_status": order.kyc_status,
        "estimated_activation_date": order.estimated_activation_date.isoformat() if order.estimated_activation_date else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "timeline": _build_timeline(order.status, order.created_at, order.estimated_activation_date),
    }


@router.get("/track/{mobile_or_ref}")
@router.get("/{mobile_or_ref}/track")
def track_order(mobile_or_ref: str, db: Session = Depends(get_db)) -> dict:
    """Lookup order by order_ref or any identifier."""
    # Try by order_ref first
    order = db.query(Order).filter(Order.order_ref == mobile_or_ref.upper()).first()
    if not order:
        # Try by partial match
        order = db.query(Order).filter(Order.order_ref.like(f"%{mobile_or_ref.upper()}%")).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"No order found for '{mobile_or_ref}'")

    bundle = []
    if order.bundle_products:
        try:
            bundle = json.loads(order.bundle_products)
        except Exception:
            bundle = []

    return {
        "order_ref": order.order_ref,
        "id": order.id,
        "status": order.status,
        "kyc_status": order.kyc_status,
        "monthly_total": order.monthly_total,
        "setup_fee": order.setup_fee,
        "contract_months": order.contract_months,
        "estimated_activation_date": order.estimated_activation_date.isoformat() if order.estimated_activation_date else None,
        "scheduled_activation_date": order.scheduled_activation_date.isoformat() if order.scheduled_activation_date else None,
        "bundle_products": bundle,
        "timeline": _build_timeline(order.status, order.created_at or datetime.utcnow(), order.estimated_activation_date),
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.get("/{order_ref}")
def get_order(order_ref: str, db: Session = Depends(get_db)) -> dict:
    """Return order detail with full timeline."""
    order = db.query(Order).filter(Order.order_ref == order_ref.upper()).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_ref} not found")

    bundle = []
    if order.bundle_products:
        try:
            bundle = json.loads(order.bundle_products)
        except Exception:
            bundle = []

    return {
        "order_ref": order.order_ref,
        "id": order.id,
        "lead_id": order.lead_id,
        "status": order.status,
        "kyc_status": order.kyc_status,
        "monthly_total": order.monthly_total,
        "setup_fee": order.setup_fee,
        "contract_months": order.contract_months,
        "estimated_activation_date": order.estimated_activation_date.isoformat() if order.estimated_activation_date else None,
        "scheduled_activation_date": order.scheduled_activation_date.isoformat() if order.scheduled_activation_date else None,
        "bundle_products": bundle,
        "timeline": _build_timeline(order.status, order.created_at or datetime.utcnow(), order.estimated_activation_date),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


@router.patch("/{order_ref}/status")
def update_order_status(order_ref: str, req: UpdateStatusRequest, db: Session = Depends(get_db)) -> dict:
    """
    Update the order status.
    If req.status is None, automatically advances to the next stage.
    """
    order = db.query(Order).filter(Order.order_ref == order_ref.upper()).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_ref} not found")

    if req.status:
        if req.status not in ORDER_STAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {ORDER_STAGES}",
            )
        order.status = req.status
    else:
        # Advance to next stage
        current_idx = ORDER_STAGES.index(order.status) if order.status in ORDER_STAGES else 0
        next_idx = min(current_idx + 1, len(ORDER_STAGES) - 1)
        order.status = ORDER_STAGES[next_idx]

    # Auto-update KYC status if stage implies it
    if order.status in ("KYC Verified", "Order Processing", "Field Tech Scheduled",
                         "Installation Complete", "Service Activated"):
        if order.kyc_status == "Pending":
            order.kyc_status = "APPROVED"

    # Set scheduled_activation_date when field tech scheduled
    if order.status == "Field Tech Scheduled" and not order.scheduled_activation_date:
        order.scheduled_activation_date = datetime.utcnow() + timedelta(days=3)

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    return {
        "order_ref": order.order_ref,
        "status": order.status,
        "kyc_status": order.kyc_status,
        "timeline": _build_timeline(order.status, order.created_at or datetime.utcnow(), order.estimated_activation_date),
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }
