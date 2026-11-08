"""
services/ocr_service.py — OCR extraction from business documents.

If Tesseract is not installed, falls back to a mock OCR mode that returns
synthetic plausible data keyed to K01-K12 applicant codes embedded in the
uploaded filename.

Mock scenario table (for demo / testing):
  K01, K04 → APPROVED  (perfect match)
  K03      → REJECTED  (GSTIN status is Cancelled in registry)
  K05      → error     (file not found / missing Udyam cert)
  K07      → REJECTED  (stale address proof date: 2026-01-15)
  K09      → FLAGGED   (GST business name ≠ Udyam enterprise name)
  Others   → APPROVED  (valid data)
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tesseract setup (graceful fallback)
# ---------------------------------------------------------------------------
_TESSERACT_AVAILABLE = False
try:
    import os
    import pytesseract
    from PIL import Image

    _tesseract_cmd = os.getenv("TESSERACT_CMD", "")
    if _tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
    # Quick sanity-check
    pytesseract.get_tesseract_version()
    _TESSERACT_AVAILABLE = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------
_GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
_UDYAM_RE = re.compile(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}")
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y",
    "%B %d, %Y", "%b %d, %Y", "%d.%m.%Y",
]

TODAY = date(2026, 7, 15)
STALE_THRESHOLD_DAYS = 90  # address proof must be <= 90 days old


# ---------------------------------------------------------------------------
# Low-level extractors (operate on raw OCR text)
# ---------------------------------------------------------------------------

def extract_gstin(text: str) -> Optional[str]:
    """Extract first valid-looking GSTIN from text."""
    match = _GSTIN_RE.search(text.upper())
    return match.group(0) if match else None


def extract_udyam_number(text: str) -> Optional[str]:
    """Extract first Udyam registration number from text."""
    match = _UDYAM_RE.search(text.upper())
    return match.group(0) if match else None


def extract_date(text: str) -> Optional[date]:
    """Try multiple date formats and return the first successfully parsed date."""
    # Find date-like substrings
    date_patterns = [
        r"\d{2}[/\-.]\d{2}[/\-.]\d{4}",
        r"\d{4}[/\-.]\d{2}[/\-.]\d{2}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}",
        r"\d{1,2}\.\d{2}\.\d{4}",
    ]
    candidates: list[str] = []
    for pat in date_patterns:
        candidates.extend(re.findall(pat, text, re.IGNORECASE))

    for raw in candidates:
        raw = raw.strip().rstrip(".")
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    return None


def extract_business_name(text: str) -> Optional[str]:
    """
    Heuristic: look for a line after keywords like 'Trade Name', 'Legal Name',
    'Enterprise Name' etc.  Returns None if nothing found.
    """
    patterns = [
        r"(?:trade\s+name|legal\s+name|enterprise\s+name|business\s+name)\s*[:\-]?\s*([^\n\r]+)",
        r"(?:name\s+of\s+(?:firm|enterprise|business))\s*[:\-]?\s*([^\n\r]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def fuzzy_name_match(name1: str, name2: str, threshold: float = 0.8) -> bool:
    """
    Simple normalised character-overlap similarity (Dice coefficient).
    Lowercases and strips punctuation before comparing.
    """
    def _normalise(s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        return " ".join(s.split())

    a = _normalise(name1)
    b = _normalise(name2)

    if a == b:
        return True
    if not a or not b:
        return False

    # Bigram Dice similarity
    def bigrams(s: str) -> set[str]:
        return {s[i : i + 2] for i in range(len(s) - 1)}

    bg_a = bigrams(a)
    bg_b = bigrams(b)
    intersection = bg_a & bg_b
    if not bg_a and not bg_b:
        return True
    denom = len(bg_a) + len(bg_b)
    if denom == 0:
        return False
    score = 2 * len(intersection) / denom
    return score >= threshold


# ---------------------------------------------------------------------------
# Mock OCR data
# ---------------------------------------------------------------------------

# Base mock GSTIN records (must be present in mock_gstin_registry.csv with
# the stated status so that KYC validation logic works correctly)
_MOCK_DATA: dict[str, dict] = {
    # K01 — perfect match → APPROVED
    "K01": {
        "gst_cert": {
            "gstin": "19JENXB8672I1ZA",
            "business_name": "Blue Lotus Kitchens Pvt Ltd",
            "status": "Active",
        },
        "udyam_cert": {
            "udyam_number": "UDYAM-WB-00-1029713",
            "enterprise_name": "Blue Lotus Kitchens Pvt Ltd",
            "enterprise_type": "Micro",
        },
        "address_proof": {"date": date(2026, 6, 15)},  # < 90 days from today
        "signatory_id": {"name": "Sunita Shah"},
    },
    # K03 — GSTIN status = Cancelled → REJECTED
    "K03": {
        "gst_cert": {
            "gstin": "37IHKXV5167L1ZS",  # Cancelled in registry
            "business_name": "Vindhya Tours & Travels",
            "status": "Cancelled",
        },
        "udyam_cert": {
            "udyam_number": "UDYAM-AP-00-8759641",
            "enterprise_name": "Riddhi Fashions Pvt Ltd",
            "enterprise_type": "Medium",
        },
        "address_proof": {"date": date(2026, 5, 20)},
        "signatory_id": {"name": "Neha Kaur"},
    },
    # K04 — perfect match → APPROVED
    "K04": {
        "gst_cert": {
            "gstin": "29HIHXN8231E1ZI",
            "business_name": "Neelgiri Physio Clinic LLP",
            "status": "Active",
        },
        "udyam_cert": {
            "udyam_number": "UDYAM-KR-00-4468149",
            "enterprise_name": "Neelgiri Physio Clinic LLP",
            "enterprise_type": "Micro",
        },
        "address_proof": {"date": date(2026, 6, 10)},
        "signatory_id": {"name": "Ayesha Nair"},
    },
    # K05 — missing Udyam cert (simulated file error)
    "K05": {
        "gst_cert": {
            "gstin": "23NCVXM2162E1ZU",
            "business_name": "Metro Polymers",
            "status": "Active",
        },
        "udyam_cert": None,  # signals "File not found"
        "address_proof": {"date": date(2026, 6, 1)},
        "signatory_id": {"name": "Venkat Patel"},
    },
    # K07 — stale address proof → REJECTED
    "K07": {
        "gst_cert": {
            "gstin": "27DGKXS9651J1Z2",
            "business_name": "Shree Legal Associates Pvt Ltd",
            "status": "Active",
        },
        "udyam_cert": {
            "udyam_number": "UDYAM-MH-00-6293684",
            "enterprise_name": "Shree Legal Associates Pvt Ltd",
            "enterprise_type": "Micro",
        },
        "address_proof": {"date": date(2026, 1, 15)},  # > 90 days old → REJECTED
        "signatory_id": {"name": "Manoj Banerjee"},
    },
    # K09 — name mismatch between GST and Udyam → FLAGGED
    "K09": {
        "gst_cert": {
            "gstin": "24RZGXM9709E1ZD",
            "business_name": "Moonlight Kitchens Pvt Ltd",
            "status": "Active",
        },
        "udyam_cert": {
            "udyam_number": "UDYAM-GJ-00-6456760",
            "enterprise_name": "Moonlight Kitchen Works",  # deliberate mismatch
            "enterprise_type": "Micro",
        },
        "address_proof": {"date": date(2026, 5, 15)},
        "signatory_id": {"name": "Amit Rao"},
    },
}

# Default mock (for K02, K06, K08, K10, K11, K12, etc.)
_DEFAULT_MOCK: dict = {
    "gst_cert": {
        "gstin": "27SJYXA0184Q1ZK",
        "business_name": "Annapurna Legal Associates",
        "status": "Active",
    },
    "udyam_cert": {
        "udyam_number": "UDYAM-MH-00-5170539",
        "enterprise_name": "Annapurna Legal Associates",
        "enterprise_type": "Medium",
    },
    "address_proof": {"date": date(2026, 6, 20)},
    "signatory_id": {"name": "Sneha Yadav"},
}


def _get_applicant_code(filename: str) -> str:
    """Extract applicant code (K01–K12) from the filename if present."""
    m = re.search(r"(K\d{2})", Path(filename).stem.upper())
    return m.group(1) if m else "K00"


def _mock_ocr(image_path: str, doc_type: str) -> dict:
    """Return synthetic OCR result without calling Tesseract."""
    code = _get_applicant_code(image_path)
    mock = _MOCK_DATA.get(code, _DEFAULT_MOCK)

    if doc_type == "udyam_cert" and mock.get("udyam_cert") is None:
        return {"error": "File not found or unreadable", "doc_type": doc_type}

    section = mock.get(doc_type)
    if section is None:
        return {"doc_type": doc_type, "raw_text": ""}

    result: dict = {"doc_type": doc_type, "applicant_code": code}
    if doc_type == "gst_cert":
        result.update(
            {
                "gstin": section.get("gstin"),
                "business_name": section.get("business_name"),
                "gstin_status": section.get("status"),
            }
        )
    elif doc_type == "udyam_cert":
        result.update(
            {
                "udyam_number": section.get("udyam_number"),
                "enterprise_name": section.get("enterprise_name"),
                "enterprise_type": section.get("enterprise_type"),
            }
        )
    elif doc_type == "address_proof":
        d = section.get("date")
        result["date"] = d.isoformat() if d else None
        result["date_valid"] = (
            (TODAY - d).days <= STALE_THRESHOLD_DAYS if d else False
        )
    elif doc_type == "signatory_id":
        result["name"] = section.get("name")

    return result


# ---------------------------------------------------------------------------
# Real OCR path
# ---------------------------------------------------------------------------

def _real_ocr(image_path: str, doc_type: str) -> dict:
    """Run Tesseract and extract fields based on doc_type."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
    except Exception as exc:
        return {"error": str(exc), "doc_type": doc_type}

    result: dict = {"doc_type": doc_type, "raw_text": text[:500]}

    if doc_type == "gst_cert":
        gstin = extract_gstin(text)
        result["gstin"] = gstin
        result["business_name"] = extract_business_name(text)
        # Try to find status keyword
        status_match = re.search(r"status\s*[:\-]?\s*(active|cancelled|suspended)", text, re.IGNORECASE)
        result["gstin_status"] = status_match.group(1).capitalize() if status_match else None

    elif doc_type == "udyam_cert":
        result["udyam_number"] = extract_udyam_number(text)
        result["enterprise_name"] = extract_business_name(text)
        type_match = re.search(r"(micro|small|medium)\s+enterprise", text, re.IGNORECASE)
        result["enterprise_type"] = type_match.group(1).capitalize() if type_match else None

    elif doc_type == "address_proof":
        d = extract_date(text)
        result["date"] = d.isoformat() if d else None
        result["date_valid"] = (
            (TODAY - d).days <= STALE_THRESHOLD_DAYS if d else False
        )

    elif doc_type == "signatory_id":
        result["name"] = extract_business_name(text) or _first_capitalised_line(text)

    return result


def _first_capitalised_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 3 and line[0].isupper():
            return line
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_from_document(image_path: str, doc_type: str) -> dict:
    """
    Main extraction function.  Uses real Tesseract if available, otherwise
    falls back to the deterministic mock mode.
    """
    if _TESSERACT_AVAILABLE:
        return _real_ocr(image_path, doc_type)
    return _mock_ocr(image_path, doc_type)
