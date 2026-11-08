"""
test_all.py — In-process integration test runner for Accel SYNC using TestClient.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from main import app

def main():
    print("==================================================")
    print("   Starting Accel SYNC In-Process Test Suite      ")
    print("==================================================")

    client = TestClient(app)
    success_count = 0
    total_tests = 0

    def assert_test(name, passed, detail=""):
        nonlocal success_count, total_tests
        total_tests += 1
        if passed:
            success_count += 1
            print(f"  [PASS] {name} - {detail}")
        else:
            print(f"  [FAIL] {name} - {detail}")

    # Test 1: Health Check
    try:
        r = client.get("/api/health")
        assert_test("Health Check", r.status_code == 200, f"Status: {r.status_code}")
    except Exception as e:
        assert_test("Health Check", False, str(e))

    # Test 2: Product Catalogue
    try:
        r = client.get("/api/products")
        data = r.json()
        assert_test("Product Catalogue", r.status_code == 200 and len(data) >= 20, f"Found {len(data)} products")
    except Exception as e:
        assert_test("Product Catalogue", False, str(e))

    # Test 3: AI Advisor Chat (English)
    try:
        payload = {
            "message": "I run a dental clinic in Kochi with 20 staff. Need fast reliable internet.",
            "language": "English"
        }
        r = client.post("/api/advisor/chat", json=payload)
        data = r.json()
        assert_test("AI Advisor Chat (English)", r.status_code == 200 and "reply" in data, f"Session: {data.get('session_id')[:8]}...")
    except Exception as e:
        assert_test("AI Advisor Chat (English)", False, str(e))

    # Test 4: AI Advisor Chat (Hindi)
    try:
        payload = {
            "message": "नमस्ते, मेरी लुधियाना में बेकरी की दुकान है। मुझे UPI और इंटरनेट चाहिए।",
            "language": "Hindi"
        }
        r = client.post("/api/advisor/chat", json=payload)
        data = r.json()
        assert_test("AI Advisor Chat (Hindi)", r.status_code == 200 and "reply" in data, f"Reply length: {len(data.get('reply', ''))}")
    except Exception as e:
        assert_test("AI Advisor Chat (Hindi)", False, str(e))

    # Test 5: Order Creation & Tracking
    try:
        order_payload = {
            "bundle_products": [{"product_id": "P01", "quantity": 1}, {"product_id": "P07", "quantity": 2}],
            "contract_months": 12
        }
        r = client.post("/api/orders", json=order_payload)
        data = r.json()
        order_ref = data.get("order_ref", "")
        assert_test("Order Creation", r.status_code == 200 and order_ref != "", f"Order Ref: {order_ref}")

        if order_ref:
            track_r = client.get(f"/api/orders/{order_ref}")
            assert_test("Order Tracking", track_r.status_code == 200, f"Status: {track_r.json().get('status')}")
    except Exception as e:
        assert_test("Order Creation & Tracking", False, str(e))

    # Test 6: Back-Office Leads & Stats
    try:
        r = client.get("/api/leads/stats")
        data = r.json()
        assert_test("Lead Stats Analytics", r.status_code == 200 and "conversion_rate" in data, f"Legacy Conversion: {data.get('conversion_rate')}%")
    except Exception as e:
        assert_test("Lead Stats Analytics", False, str(e))

    # Test 7: ML Propensity Scoring Endpoint
    try:
        r = client.get("/api/score/L00001")
        data = r.json()
        assert_test("ML Propensity Scoring", r.status_code == 200 and "propensity_score" in data, f"Score: {data.get('propensity_score')}% ({data.get('score_tier')})")
    except Exception as e:
        assert_test("ML Propensity Scoring", False, str(e))

    # Test 8: ML Feature Importances
    try:
        r = client.get("/api/score/features")
        data = r.json()
        assert_test("ML Feature Importances", r.status_code == 200 and "features" in data, f"{len(data.get('features', {}))} features identified")
    except Exception as e:
        assert_test("ML Feature Importances", False, str(e))

    # Test 9: Frontend Index Serving
    try:
        r = client.get("/")
        assert_test("Frontend Index Serving", r.status_code == 200 and "<!DOCTYPE html>" in r.text, f"Size: {len(r.text)} bytes")
    except Exception as e:
        assert_test("Frontend Index Serving", False, str(e))

    print("==================================================")
    print(f"   Validation Completed: {success_count} / {total_tests} Tests Passed!   ")
    print("==================================================")

if __name__ == "__main__":
    main()
