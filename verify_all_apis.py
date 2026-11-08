"""
verify_all_apis.py — Comprehensive end-to-end audit of all Airtel SYNC endpoints.
"""
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from db import Base, engine

# Ensure SQLite tables exist
Base.metadata.create_all(bind=engine)

client = TestClient(app)

passed = 0
failed = 0
tests = []

def test_endpoint(name, func):
    global passed, failed
    t0 = time.time()
    try:
        func()
        dt = time.time() - t0
        passed += 1
        print(f"  [PASS] {name} ({dt*1000:.1f}ms)")
    except Exception as exc:
        dt = time.time() - t0
        failed += 1
        print(f"  [FAIL] {name} ({dt*1000:.1f}ms): {exc}")

print("\n========================================================")
print("   AIRTEL SYNC / PROJECT UDYAM - COMPLETE API AUDIT")
print("========================================================\n")

# 1. Health
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200, f"Status {r.status_code}"
    assert r.json().get("status") in ["ok", "healthy"]
test_endpoint("GET /api/health", test_health)

# 2. Catalogue
def test_catalogue_list():
    r = client.get("/api/catalogue")
    assert r.status_code == 200
    data = r.json()
    assert len(data.get("products", [])) >= 20, f"Expected 20+ products, got {len(data.get('products', []))}"
test_endpoint("GET /api/catalogue", test_catalogue_list)

def test_catalogue_filters():
    r = client.get("/api/catalogue/filters")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data and "target_segments" in data
test_endpoint("GET /api/catalogue/filters", test_catalogue_filters)

def test_catalogue_detail():
    r = client.get("/api/catalogue/P01")
    assert r.status_code == 200
    assert r.json().get("product_id") == "P01"
test_endpoint("GET /api/catalogue/P01", test_catalogue_detail)

def test_catalogue_eligible():
    r = client.post("/api/catalogue/eligible", json={"num_employees": 10, "num_sites": 1, "has_gstin": True})
    assert r.status_code == 200
    assert len(r.json().get("eligible_products", [])) > 0
test_endpoint("POST /api/catalogue/eligible", test_catalogue_eligible)

def test_catalogue_bundle():
    r = client.post("/api/catalogue/bundle", json={"product_ids": ["P01", "P03"]})
    assert r.status_code == 200
    d = r.json()
    assert d.get("total_monthly_inr") > 0
test_endpoint("POST /api/catalogue/bundle", test_catalogue_bundle)

# 3. AI Advisor
session_id = None
def test_advisor_session():
    global session_id
    r = client.post("/api/advisor/session")
    assert r.status_code == 200
    session_id = r.json().get("session_id")
    assert session_id is not None
test_endpoint("POST /api/advisor/session", test_advisor_session)

def test_advisor_chat():
    global session_id
    r = client.post("/api/advisor/chat", json={
        "session_id": session_id,
        "message": "We run a dental clinic in Pune with 8 staff, need reliable broadband and cloud backup.",
        "language": "English"
    })
    assert r.status_code == 200
    d = r.json()
    assert len(d.get("reply", "")) > 10
    assert d.get("bundle_complete") is True
    assert len(d.get("recommended_products", [])) > 0
test_endpoint("POST /api/advisor/chat (AI Advisor Ultra-Fast Chat)", test_advisor_chat)

def test_advisor_get_session():
    global session_id
    r = client.get(f"/api/advisor/session/{session_id}")
    assert r.status_code == 200
    assert len(r.json().get("history", [])) >= 2
test_endpoint("GET /api/advisor/session/{id}", test_advisor_get_session)

# 4. KYC & DPDP Act 2023
lead_id = None
def test_kyc_consent():
    global lead_id
    r = client.post("/api/kyc/consent", json={
        "consent_purpose": "KYC document processing & identity cross-verification under DPDP Act 2023",
        "notice_version": "v1.0"
    })
    assert r.status_code == 200
    d = r.json()
    assert d.get("status") == "CONSENT_RECORDED"
    lead_id = d.get("lead_id")
    assert lead_id is not None
test_endpoint("POST /api/kyc/consent (DPDP Act 2023 Consent)", test_kyc_consent)

order_id = None
order_ref = None

def test_order_creation():
    global order_id, order_ref, lead_id
    r = client.post("/api/orders", json={
        "lead_id": lead_id,
        "product_ids": ["P01", "P03"],
        "contract_months": 12
    })
    assert r.status_code == 200
    d = r.json()
    order_id = d.get("order_id")
    order_ref = d.get("order_ref")
    assert order_ref is not None
    assert order_ref.startswith("ACC-2026-")
test_endpoint("POST /api/orders (Order Creation with ACC-2026 Code)", test_order_creation)

def test_kyc_upload():
    global order_id
    import io
    dummy_file = io.BytesIO(b"MOCK OCR FILE FOR TESTING AIRTEL SYNC")
    r = client.post(
        "/api/kyc/upload",
        data={"order_id": order_id, "doc_type": "gst_cert"},
        files={"file": ("test_gstin.txt", dummy_file, "text/plain")}
    )
    assert r.status_code == 200
    d = r.json()
    assert d.get("submission_id") is not None
test_endpoint("POST /api/kyc/upload (Document & OCR parser)", test_kyc_upload)

def test_kyc_verify_clean():
    # Test applicant K01 (Clean verified)
    r = client.post("/api/kyc/verify", json={
        "applicant_code": "K01",
        "gstin": "27AABCU9603R1ZM",
        "udyam_number": "UDYAM-MH-03-0012345",
        "business_name": "Apex Retailers Pvt Ltd"
    })
    assert r.status_code == 200
    d = r.json()
    assert d.get("gstin_verified") is True
    assert d.get("overall_status") in ["VERIFIED", "AUTO_APPROVED", "CLEAN"]
test_endpoint("POST /api/kyc/verify (Clean applicant K01)", test_kyc_verify_clean)

def test_kyc_verify_planted_error():
    # Test applicant K04 (Planted GSTIN error)
    r = client.post("/api/kyc/verify", json={
        "applicant_code": "K04",
        "gstin": "07AAAAA0000A1Z5",
        "business_name": "Delhi Traders"
    })
    assert r.status_code == 200
    d = r.json()
    assert d.get("overall_status") in ["FLAGGED", "FAILED", "MANUAL_REVIEW", "REJECTED"]
test_endpoint("POST /api/kyc/verify (Planted Error applicant K04)", test_kyc_verify_planted_error)

# 5. Order Tracking & Timeline
def test_order_lookup():
    global order_ref
    r = client.get(f"/api/orders/{order_ref}")
    assert r.status_code == 200
    assert r.json().get("order_ref") == order_ref
test_endpoint("GET /api/orders/{order_ref}", test_order_lookup)

def test_order_tracking():
    global order_ref
    r = client.get(f"/api/orders/{order_ref}/track")
    assert r.status_code == 200
    d = r.json()
    assert "timeline" in d
    assert len(d["timeline"]) >= 4
test_endpoint("GET /api/orders/{order_ref}/track (Milestone Tracker)", test_order_tracking)

# 6. Back-Office Leads Portal
def test_leads_list():
    r = client.get("/api/leads?limit=10")
    assert r.status_code == 200
    assert "leads" in r.json()
test_endpoint("GET /api/leads", test_leads_list)

def test_leads_stats():
    r = client.get("/api/leads/stats")
    assert r.status_code == 200
    d = r.json()
    assert "total_leads" in d
test_endpoint("GET /api/leads/stats", test_leads_stats)

# 7. ML Propensity Scoring
def test_ml_features():
    r = client.get("/api/features")
    assert r.status_code == 200
    assert "features" in r.json()
test_endpoint("GET /api/features (ML Feature Set)", test_ml_features)

def test_ml_score_lead():
    r = client.get("/api/score/L0001")
    assert r.status_code == 200
    d = r.json()
    assert "propensity_score" in d
    assert 0.0 <= d["propensity_score"] <= 100.0
test_endpoint("GET /api/score/{lead_id} (Random Forest Lead Scoring)", test_ml_score_lead)

def test_ml_predict():
    r = client.post("/api/predict", json={
        "segment": "Micro retail & services",
        "city_tier": 2,
        "employee_count": 8,
        "num_sites": 1,
        "monthly_telecom_spend_inr": 4500.0,
        "has_gstin": "Y",
        "has_udyam": "Y"
    })
    assert r.status_code == 200
    d = r.json()
    assert "propensity_score" in d
test_endpoint("POST /api/predict (Live ML Propensity Prediction)", test_ml_predict)

# 8. Web UI Static Root
def test_frontend_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "Airtel SYNC" in r.text or "Airtel" in r.text or "SYNC" in r.text
test_endpoint("GET / (Frontend Single Page Application)", test_frontend_root)

print("\n========================================================")
print(f"   AUDIT SUMMARY: {passed} PASSED, {failed} FAILED (TOTAL {passed + failed})")
print("========================================================\n")

if failed > 0:
    sys.exit(1)
