# Airtel SYNC — Full Build Plan
## Project Udyam Digital · YTL Hackathon 2026

> [!IMPORTANT]
> This is a living plan. Work through phases in order. Each phase has clear deliverables and can be demo'd independently.

---

## 0. What We're Building — At a Glance

A **mobile-first, multilingual digital acquisition & onboarding platform** for MSMEs called **Accel SYNC** that:
- Replaces a 17.6-day, ₹15,000-CAC sales process with a **sub-1-hour digital journey**
- Uses a GenAI advisor to do needs discovery in Hindi/regional languages
- Runs instant KYC via GSTIN/Udyam lookup + OCR
- Gives the owner a live order tracker instead of phone chases

---

## 1. Tech Stack Decisions

| Layer | Choice | Rationale |
|-------|---------|-----------|
| **Frontend** | React + Vite + TailwindCSS | Mobile-first, fast, component-based |
| **Backend / API** | FastAPI (Python) | Lightweight, async, easy to integrate pandas for CSV data |
| **AI Advisor** | Google Gemini API (flash model) | Multilingual, free tier, structured output |
| **OCR** | Tesseract.js (browser-side) + pytesseract (server) | No external API cost, works on KYC images |
| **Database** | SQLite (local) | Zero-setup, persists orders/leads |
| **State** | Zustand (React) | Simple global state for cart/KYC |
| **Language i18n** | react-i18next | Hindi, Tamil, Malayalam, Punjabi, Telugu, English |
| **Propensity ML** | scikit-learn (Random Forest) | Runs on smb_leads.csv, no GPU needed |

---

## 2. Project Directory Structure

```
Airtel_Sync/
├── Data/                          # Existing CSVs + KYC images
├── backend/
│   ├── main.py                    # FastAPI app entrypoint
│   ├── routers/
│   │   ├── advisor.py             # /api/advisor  — Gemini-powered chat
│   │   ├── catalogue.py           # /api/products — product listing + eligibility
│   │   ├── kyc.py                 # /api/kyc      — OCR + registry lookups
│   │   ├── orders.py              # /api/orders   — create + track orders
│   │   ├── leads.py               # /api/leads    — back-office dashboard
│   │   └── scoring.py             # /api/score    — propensity scoring
│   ├── services/
│   │   ├── gemini_service.py      # Gemini API wrapper
│   │   ├── gstin_service.py       # Mock GSTIN registry lookup
│   │   ├── udyam_service.py       # Mock Udyam registry lookup
│   │   ├── ocr_service.py         # pytesseract OCR + validation
│   │   └── propensity_model.py    # scikit-learn model training + scoring
│   ├── data/                      # Symlink or copy of Data/ CSVs
│   ├── db.py                      # SQLite models (SQLAlchemy)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Advisor.jsx        # AI Chat page
│   │   │   ├── Quote.jsx          # Quote & Checkout page
│   │   │   ├── KYC.jsx            # Smart KYC page
│   │   │   ├── Tracker.jsx        # Order Tracker page
│   │   │   └── BackOffice.jsx     # Sales/Partner dashboard (bonus)
│   │   ├── components/
│   │   │   ├── ChatBubble.jsx
│   │   │   ├── BundleCard.jsx
│   │   │   ├── AddOnToggle.jsx
│   │   │   ├── KYCUploader.jsx
│   │   │   ├── ConsentModal.jsx
│   │   │   ├── OrderTimeline.jsx
│   │   │   └── PropensityBadge.jsx
│   │   ├── store/                 # Zustand stores
│   │   ├── i18n/                  # Translation JSON files
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── docs/
│   ├── architecture.md            # System architecture + Mermaid diagram
│   ├── business_case.md           # 10-slide business case
│   └── privacy_note.md            # DPDP Act 2023 compliance 1-pager
└── Airtel_SYNC_Case.md            # (Already created)
```

---

## 3. Build Phases

### Phase 1 — Backend Foundation + Data APIs
**Est. time: 2–3 hours**

#### 1A: FastAPI Setup + Data Loaders
- [ ] `requirements.txt` with: fastapi, uvicorn, pandas, sqlalchemy, pytesseract, Pillow, google-generativeai, scikit-learn, python-multipart
- [ ] `db.py`: SQLite tables for `leads`, `orders`, `kyc_submissions`
- [ ] `catalogue.py`: Load `product_catalogue.csv` → `/api/products` with eligibility filter params
- [ ] `gstin_service.py`: Load `mock_gstin_registry.csv` → lookup by GSTIN → return name/status/address
- [ ] `udyam_service.py`: Load `mock_udyam_registry.csv` → lookup by Udyam number
- [ ] GSTIN format validator (15-char, `X` as 4th char of PAN = valid, checksum check)

#### 1B: Order + Lead APIs
- [ ] `orders.py`: POST `/api/orders` (create), GET `/api/orders/{id}` (track), PATCH `/api/orders/{id}/status`
- [ ] `leads.py`: GET `/api/leads` (back-office, with propensity score), POST `/api/leads` (save advisor session)

---

### Phase 2 — AI Advisor (Core Feature)
**Est. time: 2–3 hours**

#### Advisor Logic
- [ ] `gemini_service.py`: Gemini 1.5 Flash, system prompt engineering
- [ ] **System Prompt Strategy:**
  - Persona: "Riya, your Accel Business advisor"
  - Language detection from first message → respond in same language
  - Structured conversation flow: 5 key questions then bundle recommendation
  - Output: JSON `{recommended_products: [], reasoning: "", monthly_total: 0, language: ""}`
- [ ] **5 Discovery Questions the advisor asks:**
  1. What type of business do you run?
  2. How many locations/sites do you have?
  3. How many employees? How many need mobile SIMs?
  4. What's your biggest connectivity pain today?
  5. Do you have a GSTIN? (unlocks more products)
- [ ] Bundle recommendation engine: filter catalogue by segment/tier/GSTIN, rank by NPS data from smb_leads
- [ ] `advisor.py` router: POST `/api/advisor/chat` (streaming SSE response)

#### Frontend Chat UI
- [ ] `Advisor.jsx`: Full-screen mobile chat, language selector pill, typing indicator
- [ ] `ChatBubble.jsx`: Different styles for user/bot, product card embedded in bot message
- [ ] Bottom: "See my Quote →" CTA once recommendation made

---

### Phase 3 — Quote & Checkout
**Est. time: 1–2 hours**

- [ ] `Quote.jsx`: Shows recommended bundle as line items
- [ ] `AddOnToggle.jsx`: Toggle switches for each add-on; price updates live
- [ ] Price rules: enforce `requires_one_of` dependencies (show warning if toggle creates invalid bundle)
- [ ] Eligibility guards: grey-out products not available for user's tier/segment
- [ ] Monthly total + one-time setup fee shown clearly
- [ ] "Proceed to KYC →" CTA saves bundle to Zustand store

---

### Phase 4 — Smart KYC Module (Critical)
**Est. time: 3–4 hours — most complex**

#### 4A: Consent Screen
- [ ] `ConsentModal.jsx`: DPDP Act compliant, granular checkboxes:
  - ✅ Identity verification (GST/Udyam lookup) — required
  - ✅ Document storage for 90 days — required
  - ☐ Marketing communications — optional
  - ☐ Share with channel partner — optional
- [ ] Cannot proceed without required consents
- [ ] Consent stored with timestamp + IP hash

#### 4B: Document Upload + OCR
- [ ] `KYCUploader.jsx`: Drag-drop or camera-capture, shows preview
- [ ] `ocr_service.py`: pytesseract on uploaded images → extract fields
- [ ] **Fields to extract & validate:**
  - GST Certificate: GSTIN number, legal name, address, registration date, status
  - Udyam Certificate: Udyam number, enterprise name, type, NIC code
  - Signatory ID: Name, DOB, ID number (Aadhaar/PAN masked in display)
  - Address Proof: Address, date (must be ≤ 90 days old from 2026-07-15)

#### 4C: Cross-Validation + Planted Error Detection
- [ ] After OCR: auto-call GSTIN lookup → compare extracted GSTIN vs registry (name, status)
- [ ] After OCR: auto-call Udyam lookup → compare enterprise name vs registry
- [ ] **Planted errors to detect** (show as warnings):
  - GSTIN on certificate ≠ GSTIN in registry (tampered doc)
  - Business name mismatch between GST and Udyam certs
  - GSTIN status = Cancelled/Suspended → block
  - Address proof date > 90 days old → block
  - Signatory name on ID ≠ name on GST cert → flag for review
- [ ] KYC result: `APPROVED`, `FLAGGED` (needs human review), `REJECTED`
- [ ] `kyc.py` router: POST `/api/kyc/upload`, GET `/api/kyc/{order_id}/status`

---

### Phase 5 — Order Tracker
**Est. time: 1 hour**

- [ ] `Tracker.jsx`: Enter order ID or mobile number → see timeline
- [ ] `OrderTimeline.jsx`: Visual step tracker with dates + expected dates
- [ ] **Timeline stages:**
  1. Order Placed ✅
  2. KYC Verified ✅
  3. Order Processing ⏳
  4. Field Tech Scheduled 📅 (show expected date from `typical_install_days`)
  5. Installation Complete ✅
  6. Service Activated 🎉
- [ ] Real-time polling (every 30s) or SSE push
- [ ] "Need help?" → chat widget (don't call, chat first)

---

### Phase 6 — Bonus: Back-Office Dashboard
**Est. time: 2 hours**

- [ ] `BackOffice.jsx`: Protected route (simple password gate for demo)
- [ ] Shows dropped leads table from smb_leads.csv with:
  - Propensity Score (from Phase 7) shown as color-coded badge
  - Drop reason + stage reached
  - Recommended next action ("Call today", "Send WhatsApp", "Email quote")
- [ ] Filter by: segment, score tier, drop reason, city
- [ ] Export to CSV

---

### Phase 7 — Bonus: Lead Propensity Scoring
**Est. time: 2–3 hours**

#### ML Model (scikit-learn)
- [ ] `propensity_model.py`: Train on `smb_leads.csv`
- [ ] **Features:**
  - `segment` (one-hot encoded)
  - `has_gstin` (binary — biggest predictor, 9.6% vs 2.0% activation)
  - `has_udyam` (binary)
  - `city_tier` (1 or 2)
  - `employee_count` (binned)
  - `num_sites`
  - `monthly_telecom_spend_inr` (normalized)
  - `lead_source` (one-hot: field, website, channel partner, etc.)
  - `products_of_interest` (count of products)
  - `drop_reason` (one-hot, most important signal)
  - `stage_reached` (ordinal: lead=0, contacted=1, needs_assessed=2, etc.)
- [ ] **Target:** `outcome == "Activated"` (binary classification)
- [ ] Model: Random Forest (interpretable, handles mixed types)
- [ ] Output: probability score 0–100 → tiers: 🔴 Cold (<30), 🟡 Warm (30–70), 🟢 Hot (>70)
- [ ] `/api/score/{lead_id}` and `/api/score/batch` endpoints
- [ ] Feature importance chart for the back-office "why this score" tooltip

---

### Phase 8 — Docs & Presentation
**Est. time: 2–3 hours**

#### 8A: Architecture Diagram (Mermaid in `docs/architecture.md`)
- Full system diagram showing: User → React Frontend → FastAPI → Gemini API / GSTIN/Udyam Mock APIs / SQLite / pytesseract OCR

#### 8B: Business Case (`docs/business_case.md`)
10 slides:
1. The Opportunity: 6Cr MSMEs, 7.4% conversion today
2. Segment Prioritization: Why Professional Offices first, then Micro Retail
3. Digital Journey Overview (the SYNC platform)
4. Sample Bundles by Segment (from catalogue data)
5. Channel Harmony: Digital + Field Force co-existence model
6. Funnel Transformation: 7.4% → 20%+ target
7. Key Metrics & Targets (5 metrics)
8. Rollout Strategy: Pilot → Tier 1 cities → Tier 2 → National
9. Risk Register & Mitigations
10. Financial Summary: CAC reduction, revenue uplift

#### 8C: Privacy Note (`docs/privacy_note.md`)
DPDP Act 2023 compliance 1-pager covering:
- Consent (granular, withdraw-able, logged)
- Purpose Limitation (each data item → single purpose)
- Data Minimisation (OCR extracts only 5 fields, raw images deleted after 90 days)
- Retention (documents 90 days, masked logs indefinitely)
- Data Fiduciary obligations

---

## 4. Segment Prioritization (Key Business Decision)

Based on data analysis of `smb_leads.csv`:

| Priority | Segment | Rationale | First Bundle |
|----------|---------|-----------|--------------|
| **#1** | Professional Offices (25%) | Highest ARPU (₹4,500–8,000/mo), medium price sensitivity, GSTIN present (9.6% activation), self-serve friendly | Biz Fibre 300 + Cloud Email + Endpoint Security |
| **#2** | Micro Retail & Services (55%) | Largest volume, quick wins with simple bundles, UPI/POS need is urgent | Biz Fibre 100 / 5G AirFiber + WhatsApp API + Cloud POS |
| **#3** | Small Multi-site (15%) | Higher value but needs field assist for SD-WAN/multi-site | Biz Fibre 300 × N sites + Failover + CCTV |
| **#4** | Small Manufacturers (5%) | Leased line, long deal cycle, field-only initially | ILL 20 + Managed Firewall |

---

## 5. Key Metrics & Targets

| Metric | Current | Target (12 months) |
|--------|---------|-------------------|
| Lead-to-Activation Conversion | 7.4% | ≥ 18% (digital-only cohort) |
| Time to Activate | 17.6 days | ≤ 3 days (digital-only) |
| Customer Acquisition Cost (CAC) | ₹15,000 | ≤ ₹4,000 (digital journey) |
| Customer Follow-up Calls | 3.0× | ≤ 0.5× (tracker-driven) |
| 6-Month Churn Rate | (from data) | ≤ 8% (bundled > single product) |

---

## 6. Build Order & Dependencies

```
Phase 1 (Backend) → Phase 2 (Advisor) → Phase 3 (Quote) →
Phase 4 (KYC) → Phase 5 (Tracker) →
Phase 6 (Back-Office) + Phase 7 (Propensity) [parallel] →
Phase 8 (Docs)
```

Phases 1–5 = **Core submission** (must-have)
Phases 6–7 = **Bonus points**
Phase 8 = **Can run in parallel with coding**

---

## 7. KYC Planted Errors to Watch For

Based on the 12 applicants (K01–K12) in `kyc_documents/`:

| Error Type | What to Look For |
|-----------|-----------------|
| GSTIN status mismatch | Registry shows Cancelled/Suspended but doc says Active |
| Name mismatch | Business name on GST cert ≠ Udyam cert |
| Stale address proof | Date > 90 days before 2026-07-15 (i.e., before 2026-04-16) |
| Tampered GSTIN | OCR reads GSTIN that doesn't exist in mock registry |
| Signatory mismatch | Name on ID ≠ signing authority on GST cert |
| K05 missing Udyam | No `K05_udyam_certificate.png` in directory |

---

## 8. GSTIN Validation Algorithm

```python
import re

def validate_gstin_format(gstin: str) -> bool:
    """
    Real GSTIN structure: SS PPPPP PPPP E N Z C
    SS = state code (01-37)
    PPPPPPPPP = 9-char PAN (chars 3-11; char 6 = entity type)
    For synthetic data: 4th char of embedded PAN = 'X' (invalid real entity, accept it)
    E = entity number (1-9, A-Z)
    N = any alphanumeric
    Z = always 'Z'
    C = checksum
    """
    pattern = r'^[0-3][0-9][A-Z]{3}X[A-Z0-9]{5}[0-9][A-Z][0-9A-Z]$'
    if not re.match(pattern, gstin):
        return False
    # Luhn-style checksum validation
    return _verify_checksum(gstin)
```

---

## 9. Multilingual Support Plan

| Language | Code | Coverage |
|----------|------|---------|
| English | en | Full UI + AI responses |
| Hindi (हिंदी) | hi | Full UI + AI responses |
| Tamil (தமிழ்) | ta | AI responses only (Gemini handles) |
| Malayalam (മലയാളം) | ml | AI responses only |
| Telugu (తెలుగు) | te | AI responses only |
| Punjabi (ਪੰਜਾਬੀ) | pa | AI responses only |

The Gemini system prompt instructs: *"Detect the user's language from their first message and respond exclusively in that language for the rest of the conversation."*

---

## 10. Checklist for Demo Video (3 Minutes)

- [ ] 0:00–0:30 — Problem statement (screen: current funnel stats)
- [ ] 0:30–1:15 — AI Advisor chat in Hindi, gets bundle recommendation
- [ ] 1:15–1:45 — Quote page, toggle an add-on, see price change
- [ ] 1:45–2:15 — KYC: upload doc, see OCR extract, see planted error caught
- [ ] 2:15–2:45 — Order Tracker timeline
- [ ] 2:45–3:00 — Back-office dashboard with propensity scores
