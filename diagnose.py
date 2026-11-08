"""Fast diagnostic: checks all files exist + imports work + data loads."""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

results = []

def chk(label, fn):
    try:
        val = fn()
        results.append(("PASS", label, str(val)[:80]))
        return val
    except Exception as e:
        results.append(("FAIL", label, str(e)[:100]))
        return None

# ── File existence checks ─────────────────────────────────────────────────────
root = Path(".")
chk("backend/main.py exists",          lambda: (root/"backend/main.py").stat().st_size)
chk("backend/db.py exists",            lambda: (root/"backend/db.py").stat().st_size)
chk("backend/routers/advisor.py",      lambda: (root/"backend/routers/advisor.py").stat().st_size)
chk("backend/routers/catalogue.py",    lambda: (root/"backend/routers/catalogue.py").stat().st_size)
chk("backend/routers/kyc.py",          lambda: (root/"backend/routers/kyc.py").stat().st_size)
chk("backend/routers/orders.py",       lambda: (root/"backend/routers/orders.py").stat().st_size)
chk("backend/routers/leads.py",        lambda: (root/"backend/routers/leads.py").stat().st_size)
chk("backend/routers/scoring.py",      lambda: (root/"backend/routers/scoring.py").stat().st_size)
chk("backend/services/gstin_service",  lambda: (root/"backend/services/gstin_service.py").stat().st_size)
chk("backend/services/udyam_service",  lambda: (root/"backend/services/udyam_service.py").stat().st_size)
chk("backend/services/ocr_service",    lambda: (root/"backend/services/ocr_service.py").stat().st_size)
chk("backend/services/propensity_model", lambda: (root/"backend/services/propensity_model.py").stat().st_size)
chk("frontend/index.html exists",      lambda: (root/"frontend/index.html").stat().st_size)
chk("docs/architecture.md exists",     lambda: (root/"docs/architecture.md").stat().st_size)
chk("docs/business_case.md exists",    lambda: (root/"docs/business_case.md").stat().st_size)
chk("docs/privacy_note.md exists",     lambda: (root/"docs/privacy_note.md").stat().st_size)
chk("Data/product_catalogue.csv",      lambda: (root/"Data/product_catalogue.csv").stat().st_size)
chk("Data/smb_leads.csv",              lambda: (root/"Data/smb_leads.csv").stat().st_size)
chk("Data/mock_gstin_registry.csv",    lambda: (root/"Data/mock_gstin_registry.csv").stat().st_size)
chk("Data/mock_udyam_registry.csv",    lambda: (root/"Data/mock_udyam_registry.csv").stat().st_size)
chk("Data/kyc_documents/ (47 imgs)",   lambda: len(list((root/"Data/kyc_documents").glob("*.png"))))

# ── Import checks ─────────────────────────────────────────────────────────────
chk("import db",                lambda: __import__("db"))
chk("import routers.catalogue", lambda: __import__("routers.catalogue", fromlist=["router"]))
chk("import routers.advisor",   lambda: __import__("routers.advisor", fromlist=["router"]))
chk("import routers.kyc",       lambda: __import__("routers.kyc", fromlist=["router"]))
chk("import routers.orders",    lambda: __import__("routers.orders", fromlist=["router"]))
chk("import routers.leads",     lambda: __import__("routers.leads", fromlist=["router"]))
chk("import routers.scoring",   lambda: __import__("routers.scoring", fromlist=["router"]))
chk("import services.gstin_service",  lambda: __import__("services.gstin_service", fromlist=["lookup_gstin"]))
chk("import services.udyam_service",  lambda: __import__("services.udyam_service", fromlist=["lookup_udyam"]))
chk("import services.ocr_service",    lambda: __import__("services.ocr_service", fromlist=["extract_gstin"]))
chk("import services.propensity_model", lambda: __import__("services.propensity_model", fromlist=["train_model"]))
chk("import main (full app)",   lambda: __import__("main"))

# ── Data / Logic checks ───────────────────────────────────────────────────────
import pandas as pd
chk("product_catalogue rows",   lambda: len(pd.read_csv("Data/product_catalogue.csv")))
chk("smb_leads rows",           lambda: len(pd.read_csv("Data/smb_leads.csv")))
chk("gstin registry rows",      lambda: len(pd.read_csv("Data/mock_gstin_registry.csv")))
chk("udyam registry rows",      lambda: len(pd.read_csv("Data/mock_udyam_registry.csv")))

from services.gstin_service import lookup_gstin, validate_gstin_format
chk("GSTIN lookup K01 (Balaji Dental)", lambda: lookup_gstin("32TTNXB7384T1ZW"))
chk("GSTIN format valid",               lambda: validate_gstin_format("32TTNXB7384T1ZW"))
chk("GSTIN format invalid (bad format)", lambda: not validate_gstin_format("INVALID"))

from services.udyam_service import lookup_udyam, validate_udyam_format
chk("Udyam lookup UDYAM-KL-00-3078801", lambda: lookup_udyam("UDYAM-KL-00-3078801"))
chk("Udyam format valid",               lambda: validate_udyam_format("UDYAM-KL-00-3078801"))

from services.ocr_service import extract_gstin, extract_udyam_number
chk("OCR GSTIN regex extract",  lambda: extract_gstin("GSTIN: 32TTNXB7384T1ZW is hereby certified"))
chk("OCR Udyam regex extract",  lambda: extract_udyam_number("Reg: UDYAM-KL-00-3078801 issued"))

# Print summary
print()
print("=" * 60)
print("   ACCEL SYNC — DIAGNOSTIC REPORT")
print("=" * 60)
passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")
for status, label, detail in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon}  {label}")
    if status == "FAIL":
        print(f"       ERROR: {detail}")
    elif detail and status == "PASS" and not detail.startswith("<module"):
        print(f"       {detail}")
print()
print(f"  RESULT: {passed} PASS  |  {failed} FAIL  |  {len(results)} total")
print("=" * 60)

