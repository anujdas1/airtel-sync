import sys, traceback
sys.path.insert(0, 'backend')

tests = []

# 1. Import main
try:
    from main import app
    tests.append(('Backend main.py imports cleanly', True, ''))
except Exception as e:
    tests.append(('Backend main.py imports cleanly', False, str(e)))

# 2. All routers importable
for router_name in ['catalogue', 'advisor', 'kyc', 'orders', 'leads', 'scoring']:
    try:
        mod = __import__(f'routers.{router_name}', fromlist=['router'])
        tests.append((f'Router: {router_name}.py', True, 'OK'))
    except Exception as e:
        tests.append((f'Router: {router_name}.py', False, str(e)[:100]))

# 3. All services importable
for svc in ['gstin_service', 'udyam_service', 'ocr_service', 'propensity_model']:
    try:
        mod = __import__(f'services.{svc}', fromlist=[svc])
        tests.append((f'Service: {svc}.py', True, 'OK'))
    except Exception as e:
        tests.append((f'Service: {svc}.py', False, str(e)[:100]))

# 4. GSTIN Registry lookup
try:
    from services.gstin_service import lookup_gstin, validate_gstin_format
    result = lookup_gstin('32TTNXB7384T1ZW')
    tests.append(('GSTIN lookup (K01 Balaji Dental)', result is not None, str(result)[:80] if result else 'Not found'))
    # Test format validation
    valid = validate_gstin_format('32TTNXB7384T1ZW')
    tests.append(('GSTIN format validation', valid, '32TTNXB7384T1ZW -> valid'))
except Exception as e:
    tests.append(('GSTIN lookup', False, str(e)[:100]))

# 5. Udyam Registry lookup
try:
    from services.udyam_service import lookup_udyam
    result = lookup_udyam('UDYAM-KL-00-3078801')
    tests.append(('Udyam lookup (K01)', result is not None, str(result)[:80] if result else 'Not found'))
except Exception as e:
    tests.append(('Udyam lookup', False, str(e)[:100]))

# 6. OCR Service
try:
    from services.ocr_service import extract_gstin, extract_udyam_number
    g = extract_gstin('GSTIN: 32TTNXB7384T1ZW is hereby certified')
    u = extract_udyam_number('Registration No: UDYAM-KL-00-3078801 issued')
    tests.append(('OCR extract GSTIN regex', g == '32TTNXB7384T1ZW', f'Found: {g}'))
    tests.append(('OCR extract Udyam regex', u == 'UDYAM-KL-00-3078801', f'Found: {u}'))
except Exception as e:
    tests.append(('OCR Service', False, str(e)[:100]))

# 7. Propensity Model
try:
    from services.propensity_model import train_model, score_lead, get_score_tier
    from pathlib import Path
    csv_path = str(Path('Data/smb_leads.csv'))
    metrics = train_model(csv_path)
    tests.append(('ML model trains on smb_leads.csv', 'accuracy' in metrics, str(metrics)[:100]))
    score = score_lead({'segment': 'Professional offices', 'has_gstin': 'Y', 'has_udyam': 'Y', 'city_tier': 1, 'employee_count': 20, 'num_sites': 1, 'monthly_telecom_spend_inr': 4500, 'lead_source': 'Website form', 'products_of_interest': 'P02;P16', 'stage_reached': 'Needs assessed'})
    tier = get_score_tier(score)
    tests.append(('ML propensity score lead', isinstance(score, (int, float)), f'{score:.1f}% -> {tier}'))
except Exception as e:
    tests.append(('ML Propensity Model', False, str(e)[:100]))

# 8. TestClient route tests
try:
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get('/api/health')
    tests.append(('GET /api/health', r.status_code == 200, f'HTTP {r.status_code}'))

    r = client.get('/api/products')
    data = r.json()
    count = len(data) if isinstance(data, list) else '?'
    tests.append(('GET /api/products', r.status_code == 200, f'{count} products returned'))

    r = client.post('/api/advisor/chat', json={'message': 'I run a dental clinic in Kochi with 20 staff. Need internet.', 'language': 'English'})
    data = r.json()
    tests.append(('POST /api/advisor/chat', r.status_code == 200 and 'reply' in data, data.get('reply', '')[:70]))

    r = client.post('/api/orders', json={'bundle_products': [{'product_id': 'P01', 'quantity': 1}, {'product_id': 'P07', 'quantity': 2}], 'contract_months': 12})
    data = r.json()
    ref = data.get('order_ref', '')
    tests.append(('POST /api/orders', r.status_code == 200 and bool(ref), ref))

    if ref:
        r2 = client.get(f'/api/orders/{ref}')
        tests.append((f'GET /api/orders/{{ref}} (tracker)', r2.status_code == 200, r2.json().get('status', '')[:60]))

    r = client.get('/api/leads/stats')
    data = r.json()
    tests.append(('GET /api/leads/stats', r.status_code == 200, str(data)[:80]))

    r = client.get('/api/score/L00001')
    data = r.json()
    tests.append(('GET /api/score/L00001', r.status_code == 200 and 'propensity_score' in data, f"{data.get('propensity_score', '?')}% {data.get('score_tier', '?')}"))

    r = client.get('/')
    tests.append(('GET / (frontend HTML)', r.status_code == 200 and 'DOCTYPE' in r.text, f'{len(r.text)} bytes'))

except Exception as e:
    tests.append(('TestClient suite', False, traceback.format_exc()[:200]))

# Print results
print()
print('=== ACCEL SYNC — INTEGRATION TEST RESULTS ===')
passed = sum(1 for _, ok, _ in tests if ok)
for name, ok, detail in tests:
    icon = '[PASS]' if ok else '[FAIL]'
    print(f'  {icon}  {name}')
    if detail:
        print(f'          {detail}')
print()
print(f'  RESULT: {passed}/{len(tests)} tests passed')

