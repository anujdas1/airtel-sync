"""
services/udyam_service.py — Mock Udyam registry lookup and validation.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Load registry once at import time
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "Data"
_UDYAM_CSV = _DATA_DIR / "mock_udyam_registry.csv"

_registry_df: pd.DataFrame | None = None


def _load_registry() -> pd.DataFrame:
    global _registry_df
    if _registry_df is None:
        _registry_df = pd.read_csv(_UDYAM_CSV, dtype=str).fillna("")
        _registry_df.columns = [c.strip().lower().replace(" ", "_") for c in _registry_df.columns]
    return _registry_df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_udyam(udyam_number: str) -> dict | None:
    """Return registry record for the given Udyam number or None."""
    df = _load_registry()
    udyam_number = udyam_number.strip().upper()
    row = df[df["udyam_number"] == udyam_number]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "udyam_number": r.get("udyam_number", ""),
        "enterprise_name": r.get("enterprise_name", ""),
        "enterprise_type": r.get("enterprise_type", ""),
        "major_activity": r.get("major_activity", ""),
        "nic_description": r.get("nic_description", ""),
        "state": r.get("state", ""),
        "city": r.get("city", ""),
        "date_of_registration": r.get("date_of_registration", ""),
    }


def validate_udyam_format(udyam_number: str) -> bool:
    """
    Validate Udyam registration number format.
    Format: UDYAM-[A-Z]{2}-00-[0-9]{7}
    District code 00 = synthetic/mock.
    """
    pattern = r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$"
    return bool(re.match(pattern, udyam_number.strip().upper()))
