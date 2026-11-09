# Accel SYNC — Project Udyam Digital

> **Making small businesses go digital in one sitting.**  
> *YTL Hackathon 2026 · Enterprise Track A (Airtel SYNC)*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React_18-61DAFB?logo=react)](https://react.dev/)
[![Gemini](https://img.shields.io/badge/AI-Google_Gemini_3.8_Flash-4285F4?logo=google)](https://ai.google.dev/)
[![Compliance](https://img.shields.io/badge/Compliance-DPDP_Act_2023-blue)](docs/privacy_note.md)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Executive Summary

India is home to **6.3 crore+ MSMEs** (kiranas, clinics, coaching centres, restaurants, and small manufacturers) contributing 30% of national GDP. While telecom operators excel at enterprise sales, acquiring small businesses has historically been slow, paper-heavy, and cost-inefficient:

* **Current Legacy Funnel:** 5,000 leads → 368 activations (**7.36% conversion**)
* **Steepest Chokepoint:** **44% drop-off** between Needs Assessed and Quote Accepted due to complex PDF product codes
* **Cycle Time:** Average of **17.6 days** with **3+ customer status chases**
* **Customer Acquisition Cost:** **₹15,000 CAC** per activated SMB

**Accel SYNC** solves this by delivering an end-to-end, digital-first acquisition and onboarding platform on mobile. Business owners discover tailored bundles, complete instant KYC, and track activation in **one sitting (<15 minutes)**.

```
Legacy Journey: [5,000 Leads] ──> [3,406 Contacted] ──> [1,974 Needs] ──(44% Drop)──> [861 Quotes] ──> [368 Activated (7.4%)]
Accel SYNC:     [Digital Onboarding] ──> [AI Advisor] ──> [Instant Quote] ──> [Smart KYC] ──> [18%+ Target Conversion]
```

---

## 🚀 Core Features

### 1. 🤖 AI Advisor (Kaberi)
* **Multilingual GenAI Engine:** Powered by **Google Gemini 3.8 Flash** with support for English, Hindi (हिंदी), Tamil (தமிழ்), Telugu (తెలుగు), and Punjabi (ਪੰਜਾਬੀ).
* **Conversational Needs Discovery:** Asks 4–5 intuitive questions about business type, locations, employee count, and pain points rather than technical telecom codes.
* **Intelligent Bundle Matching:** Recommends optimal bundles directly from `product_catalogue.csv` with clear, jargon-free explanations.
* **Omnichannel Access:** Interactive Web Chat, Web Speech API Voice recognition/read-aloud, and simulated WhatsApp interface.
* **1-Click Judge Presets:** Pre-configured scenarios (Dental Clinic in Kochi, Bakery in Ludhiana, 5-store restaurant chain, Auto-parts factory).

### 2. 🛒 Quote & Checkout
* **Transparent Single Monthly Price:** Clear itemized breakdown eliminating confusing quotation PDFs.
* **Interactive Add-On Configurator:** Toggle 4G/5G Failover, Cloud CCTV, WhatsApp Business API, Cloud POS, Static IP, and Endpoint Security live.
* **Contract Commitment Savings:** Live discounts (10% off for 12 months, 15% off for 24 months) + 18% GST input tax credit calculation.
* **Automated Eligibility Engine:** Enforces catalogue rules (e.g. Failover requires active fibre; minimum employee/site constraints).

### 3. 📑 Smart KYC & OCR Verification
* **DPDP Act, 2023 Consent Screen:** Statutory consent checkboxes with audit timestamping, data minimization, and 90-day auto-purge notices.
* **Real-Time Registry Lookups:** Instant mock API verification against 3,534 GSTIN records and 2,723 Udyam registry records.
* **Automated Document OCR:** Tesseract OCR pipeline extracting legal names, GSTIN format, registration dates, and utility bill dates.
* **Planted Error Catching:** Accurately catches planted errors in specimen test applicants (`K01`–`K12`):
  * **`K01` (Balaji Dental Care):** ✅ **APPROVED** (clean registry cross-validation)
  * **`K03` (Star Electronics):** ❌ **REJECTED** (GSTIN cancelled in registry)
  * **`K05` (Zenith Diagnostics):** ⚠️ **ERROR_MISSING** (missing Udyam certificate image)
  * **`K07` (Green Leaf Physio):** ❌ **REJECTED** (utility bill dated >90 days old from 2026-07-15)
  * **`K09` (Riddhi Fashions):** ⚠️ **FLAGGED** (Trade Name mismatch between GST and Udyam certs)

### 4. 📦 Live Self-Service Order Tracker
* **Customer Status Chase Killer:** Real-time visibility into the 6-stage lifecycle:
  1. *Order Placed* → 2. *Smart KYC Verified* → 3. *Hardware Dispatched* → 4. *Field Engineer Scheduled* → 5. *Fibre Splice & Tested* → 6. *Services Activated*
* **Milestone Simulator:** Fast-forward button to demonstrate full fulfillment transitions in under 30 seconds during evaluations.

### 5. 💼 Back-Office & ML Propensity Scoring (Bonus)
* **Field Sales & Channel Co-Pilot:** Prioritizes 5,000 leads from `smb_leads.csv` for human field agent follow-ups.
* **Machine Learning Propensity Model:** Trained Random Forest classifier categorizing dropped leads into **Hot (>70%)**, **Warm (30–70%)**, and **Cold (<30%)** tiers.
* **One-Click Agent Actions:** Quick dispatch buttons (`📞 Call within 2h`, `💬 Send WhatsApp`, `Assign to Partner`).

---

## 🛠️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│                   Client Layer                         │
│   • React 18 (SPA)         • Tailwind CSS              │
│   • Web Speech API (STT/TTS)• WhatsApp Interface Mode │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / JSON
┌──────────────────────────▼─────────────────────────────┐
│                 FastAPI Backend                        │
│   • Lifespan Model Loader  • CORS Middleware           │
│   • REST Routers (Catalogue, Advisor, KYC, Orders)     │
└──────────┬─────────────────────────────┬───────────────┘
           │                             │
┌──────────▼──────────┐       ┌──────────▼───────────────┐
│     AI Services     │       │     Data & Registries    │
│ • Google Gemini     │       │ • SQLite Database        │
│   3.8 Flash         │       │ • Mock GSTIN Registry    │
│ • Tesseract OCR     │       │ • Mock Udyam Registry    │
│ • Scikit-Learn RF   │       │ • Product Catalogue      │
└─────────────────────┘       └──────────────────────────┘
```

---

## 💻 Local Setup & Execution

### Prerequisites
* Python 3.10+
* Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/airtel-sync.git
cd airtel-sync
```

### 2. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Copy the example environment template:
```bash
cp backend/.env.example backend/.env
```
Open `backend/.env` and paste your Google Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite:///./accel_sync.db
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```
*(Note: If no API key is provided, the application runs on its internal rule-based advisor automatically without breaking).*

### 4. Run the Server
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Access the Platform
* **Web UI:** [http://localhost:8000/](http://localhost:8000/)
* **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Verification & Diagnostics

Run the automated diagnostic suite to verify all 44 test checkpoints:
```bash
python diagnose.py
```
Expected output:
```
============================================================
   ACCEL SYNC — DIAGNOSTIC REPORT
============================================================
  ✅  44 PASS  |  0 FAIL  |  44 total
============================================================
```

---

## 🔒 Data Privacy & Security (DPDP Act, 2023)

Accel SYNC is engineered around the core principles of India's **Digital Personal Data Protection Act, 2023**:
* **Consent Architecture (Section 6):** Granular, unbundled checkboxes separating statutory identity verification from optional communications.
* **Purpose Limitation:** Business identifiers are strictly queried for registry cross-matching and discarded from session memory.
* **Data Minimization:** OCR extracts only 5 mandatory fields; PAN characters are masked.
* **Retention:** Raw specimen images are encrypted at rest with AES-256 and subject to a 90-day automated purge policy.

Full details available in [docs/privacy_note.md](docs/privacy_note.md).

---

## 📂 Project Structure

```
Airtel_Sync/
├── Data/                          # Synthetic dataset files
│   ├── kyc_documents/             # 47 specimen KYC PNG images (K01-K12)
│   ├── mock_gstin_registry.csv    # 3,534 GSTIN mock registry records
│   ├── mock_udyam_registry.csv    # 2,723 Udyam mock registry records
│   ├── product_catalogue.csv      # 25 Accel Business products
│   └── smb_leads.csv              # 5,000 synthetic SMB leads
├── backend/                       # FastAPI application
│   ├── routers/                   # API endpoint modules
│   │   ├── advisor.py             # Gemini AI chat router
│   │   ├── catalogue.py           # Product catalogue & eligibility router
│   │   ├── kyc.py                 # Document upload & verification router
│   │   ├── leads.py               # Back-office lead management router
│   │   ├── orders.py              # Order creation & tracking router
│   │   └── scoring.py             # ML Propensity scoring router
│   ├── services/                  # Business logic & AI services
│   │   ├── gstin_service.py       # GSTIN lookup & format validation
│   │   ├── udyam_service.py       # Udyam lookup & format validation
│   │   ├── ocr_service.py         # Document OCR & planted error logic
│   │   └── propensity_model.py    # Random Forest ML model (scikit-learn)
│   ├── db.py                      # SQLAlchemy database models
│   ├── main.py                    # Application entrypoint
│   └── requirements.txt           # Python dependencies
├── docs/                          # Technical & statutory documentation
│   ├── architecture.md            # Complete architecture & data flow diagrams
│   ├── business_case.md           # 10-slide business case & financial model
│   └── privacy_note.md            # DPDP Act 2023 compliance 1-pager
├── frontend/                      # Mobile-first web application
│   └── index.html                 # Self-contained single page application
├── .gitignore                     # Git ignore rules (protects API keys & DB)
├── diagnose.py                    # 44-point automated test script
├── run_tests.py                   # In-process test runner
└── README.md                      # Repository documentation
```

---

## 👥 Authors
* Developed for **YTL Hackathon 2026 · Enterprise Track A (Airtel SYNC)**

