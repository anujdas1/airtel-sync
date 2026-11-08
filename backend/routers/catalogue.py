"""
routers/catalogue.py — Product catalogue endpoints for Accel SYNC.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Catalogue"])

# ---------------------------------------------------------------------------
# Data — loaded at startup via main.py lifespan; also loaded lazily here
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "Data"
_CATALOGUE_CSV = _DATA_DIR / "product_catalogue.csv"

_catalogue_df: pd.DataFrame | None = None


def load_catalogue() -> pd.DataFrame:
    global _catalogue_df
    if _catalogue_df is None:
        df = pd.read_csv(_CATALOGUE_CSV, dtype=str).fillna("")
        df.columns = [c.strip() for c in df.columns]
        # Numeric columns
        for col in [
            "price_min_inr_per_month",
            "price_max_inr_per_month",
            "one_time_setup_inr",
            "min_contract_months",
            "min_employees",
            "min_sites",
            "typical_install_days",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        _catalogue_df = df
    return _catalogue_df


def get_catalogue() -> pd.DataFrame:
    return load_catalogue()


# ---------------------------------------------------------------------------
# Eligibility helpers
# ---------------------------------------------------------------------------

def _eligible(row: pd.Series, segment: str | None, city_tier: int | None, has_gstin: bool | None) -> bool:
    """Return True if the product row matches the given filter criteria."""
    if city_tier is not None:
        tiers = [t.strip() for t in str(row["available_city_tiers"]).split(";") if t.strip()]
        if str(city_tier) not in tiers:
            return False

    if segment is not None:
        segs = [s.strip().lower() for s in str(row["target_segments"]).split(";") if s.strip()]
        if segment.lower() not in segs:
            return False

    if has_gstin is not None and not has_gstin:
        if str(row.get("requires_gstin", "N")).strip().upper() == "Y":
            return False

    return True


def _row_to_dict(row: pd.Series) -> dict:
    return {
        "product_id": row["product_id"],
        "category": row["category"],
        "product_name": row["product_name"],
        "description": row["description"],
        "unit": row["unit"],
        "price_min_inr_per_month": float(row["price_min_inr_per_month"]),
        "price_max_inr_per_month": float(row["price_max_inr_per_month"]),
        "one_time_setup_inr": float(row["one_time_setup_inr"]),
        "min_contract_months": int(row["min_contract_months"]),
        "available_city_tiers": row["available_city_tiers"],
        "min_employees": int(row["min_employees"]),
        "min_sites": int(row["min_sites"]),
        "requires_gstin": row["requires_gstin"],
        "requires_one_of": row.get("requires_one_of", ""),
        "typical_install_days": int(row["typical_install_days"]),
        "target_segments": row["target_segments"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/catalogue/filters")
@router.get("/products/filters")
def get_filters() -> dict:
    """Return available categories and target segments."""
    df = get_catalogue()
    categories = sorted(list(set(df["category"].dropna().tolist())))
    segments = ["micro", "prof", "multi", "mfg"]
    return {"categories": categories, "target_segments": segments}


@router.get("/catalogue")
@router.get("/products")
def list_products(
    segment: Optional[str] = Query(None, description="micro|prof|multi|mfg"),
    city_tier: Optional[int] = Query(None, description="1 or 2"),
    has_gstin: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
) -> dict:
    """Return all products, optionally filtered."""
    df = get_catalogue()

    result = []
    for _, row in df.iterrows():
        if not _eligible(row, segment, city_tier, has_gstin):
            continue
        if category and row["category"].lower() != category.lower():
            continue
        result.append(_row_to_dict(row))

    return {"products": result, "total": len(result)}


@router.get("/catalogue/{product_id}")
@router.get("/products/{product_id}")
def get_product(product_id: str) -> dict:
    """Return a single product by ID."""
    df = get_catalogue()
    row = df[df["product_id"] == product_id.upper()]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return _row_to_dict(row.iloc[0])


@router.get("/bundles/recommended")
def recommend_bundles(
    segment: str = Query(..., description="micro|prof|multi|mfg"),
    city_tier: int = Query(..., description="1 or 2"),
    has_gstin: bool = Query(False),
) -> dict:
    """
    Return top-3 bundle suggestions for a given business profile.

    Strategy:
    1. Filter eligible products.
    2. Score each product: priority = Connectivity > Communication > Cloud & Productivity > Security > IoT
    3. Build a primary connectivity product + 1-2 add-on products.
    4. Return 3 bundle variants.
    """
    df = get_catalogue()

    eligible = [row for _, row in df.iterrows() if _eligible(row, segment, city_tier, has_gstin)]

    if not eligible:
        return {"bundles": [], "message": "No eligible products for given criteria"}

    # Category priority order
    _CAT_PRIORITY = {
        "Connectivity": 0,
        "Communication": 1,
        "Cloud & Productivity": 2,
        "Security": 3,
        "IoT & Physical": 4,
    }

    eligible_sorted = sorted(
        eligible,
        key=lambda r: (_CAT_PRIORITY.get(r["category"], 99), float(r["price_min_inr_per_month"])),
    )

    connectivity = [r for r in eligible_sorted if r["category"] == "Connectivity"]
    addons = [r for r in eligible_sorted if r["category"] != "Connectivity"]

    bundles: list[dict] = []

    # Build 3 bundles: starter, standard, premium
    _tiers = [
        ("Starter", connectivity[:1], addons[:1]),
        ("Standard", connectivity[:1], addons[:2]),
        ("Premium", connectivity[1:2] if len(connectivity) > 1 else connectivity[:1], addons[:3]),
    ]

    for name, conn_items, addon_items in _tiers:
        products_in_bundle = conn_items + addon_items
        if not products_in_bundle:
            continue

        monthly = sum(float(r["price_min_inr_per_month"]) for r in products_in_bundle)
        setup = sum(float(r["one_time_setup_inr"]) for r in products_in_bundle)

        bundles.append(
            {
                "bundle_name": f"{name} Bundle",
                "products": [_row_to_dict(r) for r in products_in_bundle],
                "product_ids": [r["product_id"] for r in products_in_bundle],
                "monthly_total_min": round(monthly, 2),
                "setup_fee": round(setup, 2),
            }
        )

    return {"bundles": bundles[:3], "segment": segment, "city_tier": city_tier, "has_gstin": has_gstin}


class EligibilityRequest(BaseModel):
    num_employees: Optional[int] = 5
    num_sites: Optional[int] = 1
    has_gstin: Optional[bool] = False
    segment: Optional[str] = None
    city_tier: Optional[int] = 1


@router.post("/catalogue/eligible")
@router.post("/products/eligible")
def check_eligible(req: EligibilityRequest) -> dict:
    """Return all products matching business criteria."""
    df = get_catalogue()
    eligible = []
    for _, row in df.iterrows():
        if _eligible(row, req.segment, req.city_tier, req.has_gstin):
            eligible.append(_row_to_dict(row))
    return {"eligible_products": eligible, "count": len(eligible)}


class BundlePriceRequest(BaseModel):
    product_ids: list[str]


@router.post("/catalogue/bundle")
@router.post("/products/bundle")
def calculate_bundle(req: BundlePriceRequest) -> dict:
    """Calculate transparent total price and setup fees for custom product list."""
    df = get_catalogue()
    total_monthly = 0.0
    total_setup = 0.0
    products = []
    for pid in req.product_ids:
        row = df[df["product_id"] == pid.upper()]
        if not row.empty:
            r = row.iloc[0]
            total_monthly += float(r["price_min_inr_per_month"])
            total_setup += float(r["one_time_setup_inr"])
            products.append(_row_to_dict(r))
    return {
        "product_ids": req.product_ids,
        "products": products,
        "total_monthly_inr": round(total_monthly, 2),
        "total_setup_inr": round(total_setup, 2),
    }
