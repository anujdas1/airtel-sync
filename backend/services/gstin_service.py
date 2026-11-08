"""
services/gstin_service.py — Mock GSTIN registry lookup and validation.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Load registry once at import time
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "Data"
_GSTIN_CSV = _DATA_DIR / "mock_gstin_registry.csv"

_registry_df: pd.DataFrame | None = None


def _load_registry() -> pd.DataFrame:
    global _registry_df
    if _registry_df is None:
        _registry_df = pd.read_csv(_GSTIN_CSV, dtype=str).fillna("")
        # Normalise column names to lowercase snake_case
        _registry_df.columns = [c.strip().lower().replace(" ", "_") for c in _registry_df.columns]
    return _registry_df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_gstin(gstin: str) -> dict | None:
    """Return registry record for the given GSTIN or None."""
    df = _load_registry()
    gstin = gstin.strip().upper()
    row = df[df["gstin"] == gstin]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "gstin": r.get("gstin", ""),
        "legal_name": r.get("legal_name", ""),
        "trade_name": r.get("trade_name", ""),
        "constitution": r.get("constitution", ""),
        "address": r.get("principal_place_of_business", ""),
        "state": r.get("state", ""),
        "registration_date": r.get("registration_date", ""),
        "status": r.get("status", ""),
    }


def validate_gstin_format(gstin: str) -> bool:
    """
    Validate 15-character GSTIN format.
    Format: SSAAAXPPPPPENZC
      SS  = state code (01–37)
      AAA = first 3 chars of PAN (alpha)
      X   = entity type char (always X in mock data)
      PPPPP = last 5 of PAN (alpha-num)
      E   = entity number (alphanum)
      N   = alphanum
      Z   = always Z
      C   = checksum (alphanum)
    """
    if not gstin or len(gstin) != 15:
        return False
    pattern = r"^([0-3][0-9])[A-Z]{3}[A-Z0-9][A-Z]\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]$"
    if not re.match(pattern, gstin.upper()):
        return False
    state_code = int(gstin[:2])
    if state_code < 1 or state_code > 37:
        return False
    return True


def get_gstin_status(gstin: str) -> str | None:
    """Return the status string ('Active', 'Cancelled', 'Suspended') or None."""
    record = lookup_gstin(gstin)
    if record is None:
        return None
    return record.get("status")
