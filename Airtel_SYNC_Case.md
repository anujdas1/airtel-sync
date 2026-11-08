# Airtel SYNC — Where Ingenuity Meets Scale
## Case Study: Project Udyam Digital
**Making small businesses go digital in one sitting**

* **Competition:** YTL HACKATHON 2026 · ENTERPRISE TRACK A
* **Case Study & Problem Statement:** Prepared by Ankit Srivastava · October 2026
* **Platform Partner:** Unstop
* **Organization:** Fictional operator, Accel Telecom (B2B arm: Accel Business)
* *Note:* All figures and data are synthetic and built for this exercise; they are not actual company data.

---

## 1. Context

Accel Telecom leads India's mobile market and is a top-2 player in home broadband. Its enterprise arm, **Accel Business**, serves large corporates well but has a small share of India's 6 crore+ micro, small and medium enterprises (MSMEs): kirana stores, clinics, coaching centres, small manufacturers, CA firms, and restaurants.

These businesses increasingly need more than a SIM. A typical clinic or retail shop now wants:
* Fixed broadband or a leased line
* A few business SIMs
* A WhatsApp/SMS channel to reach customers
* Cloud email and storage
* Basic cybersecurity
* CCTV or POS connectivity

Today, they buy each piece from a different vendor, often from a local reseller, with no single bill or support number.

Accel Business already offers most of these products, but sells them one at a time through a field sales force built for large accounts. The journey for a small business owner is slow and paper-heavy:
* **Needs Discovery:** Discovered in a visit by a sales executive, who often pitches whatever is on target that month.
* **Quotation:** A quote takes 3–5 days and arrives as a PDF with technical product codes the owner does not understand.
* **KYC:** Needs GST certificate, Udyam registration, address proof, and signatory ID, collected physically or over email.
* **Installation & Activation:** Takes 10–14 days on average, requiring 3–4 follow-up calls from the customer.
* **Billing & Support:** Each product is billed and supported separately after activation.

**Result:** Cost to acquire an SMB is high, conversion is low, and a large share of interested prospects drop out before activation. Competitors and digital-first players are starting to offer instant online sign-up for single products.

---

## 2. The Problem Statement

> **Design and build a digital-first acquisition and onboarding journey that lets a small business owner discover the right bundle, buy it, and get it activated with minimal human effort — on a phone, in their preferred language.**

---

## 3. Key Questions to Address

1. **Prioritization & Packaging:** Which MSME segments should Accel Business prioritise first, and what bundle (products, price point, contract length) fits each?
2. **Conversational Needs Discovery:** How should needs discovery work without a salesperson? Think of a conversational advisor (chat or voice, in Hindi and regional languages) that asks a few questions and recommends a bundle with a clear monthly price.
3. **Instant & Compliant KYC:** How can KYC and documentation be made near-instant (e.g. GSTIN/Udyam lookup, document OCR, DigiLocker, e-sign) while staying compliant with the **DPDP Act, 2023** (consent, purpose limitation, data minimisation)?
4. **Channel Harmony:** What role should the existing field force and local channel partners play, so the digital journey adds to them instead of competing with them?
5. **Success Metrics:** How will you measure success? Define 3–5 metrics that matter (e.g., lead-to-activation conversion, time to activate, cost of acquisition, 6-month churn) and the targets you would set.

---

## 4. Build Challenge (Prototype Requirements)

Build a working prototype of the journey covering at least:

| Module | Description |
| :--- | :--- |
| **Advisor** | A GenAI-powered assistant that asks about the business (type, size, locations, current tools) and recommends a bundle from the product catalogue, explaining why in plain language. |
| **Quote & Checkout** | A single, transparent monthly price with add-ons the owner can toggle. |
| **Smart KYC** | Document upload with extraction and validation, mocked lookups of GSTIN and Udyam data, and a clear consent screen. |
| **Tracker** | An order status view the owner can check instead of calling support. |

### Stretch Goals (Bonus Points):
* **Alternative Front-Ends:** A voice or WhatsApp front-end interface.
* **Back-Office Dashboard:** A view for sales or partners showing leads the advisor could not close.
* **Lead Propensity Scoring:** A machine learning or rule-based score to indicate which dropped leads sales teams should call first.

---

## 5. Submission Deliverables

1. **Working Prototype:** Demo video of 3 minutes max + code repository.
2. **Solution Architecture Diagram:** Main components and data flows of the digital journey.
3. **Business Case (Max 10 Slides):** Target customer, value proposition, pricing/savings, rollout strategy, and risk mitigation.
4. **Data Privacy & Security Note (1 Pager):** Architectural and design choices made to ensure compliance with DPDP Act, 2023.

---

## 6. Provided Synthetic Data

The dataset package `YTL_TrackA_Udyam_Digital_Data.zip` includes:

| File | Size | Usage Description |
| :--- | :--- | :--- |
| `product_catalogue.csv` | 25 products | Advisor recommendations and quotes: price ranges, setup fees, contract length, eligibility rules (city tier, size, GSTIN needed), and product dependencies. |
| `smb_leads.csv` | 5,000 leads | One quarter of SMB leads: profile, source, funnel stage reached, drop reason, stage dates; for activated leads: bundle bought, value, 6-month churn, and NPS. |
| `mock_gstin_registry.csv` | 3,534 records | Backing data for mock GSTIN lookup API (legal name, address, status including cancelled/suspended). |
| `mock_udyam_registry.csv` | 2,723 records | Backing data for mock Udyam lookup API. |
| `kyc_documents/` | 47 images, 12 applicants | Specimen GST and Udyam certificates, signatory IDs, and utility bills for OCR and validation (some contain deliberately planted problems). |

*(Note: Evaluators have a separate hidden test pack `YTL_TrackA_Judges_Only.zip` with 15 live test scenarios, KYC answer keys, planted lead signals, and verification scripts).*

---

## 7. Appendix A1: Current SMB Acquisition Funnel

*Data based on 5,000 leads → 368 activations, Apr–Jun 2026 (`smb_leads.csv`, Tier 1–2 cities):*

```
[5,000] Leads Generated
   │ (68% conversion)
   ▼
[3,406] Contacted
   │ (58% conversion)
   ▼
[1,974] Needs Assessed
   │ (44% conversion) ◄─── STEEPEST DROP OFF
   ▼
  [861] Quote Accepted
   │ (68% conversion)
   ▼
  [588] KYC Complete
   │ (63% conversion)
   ▼
  [368] Activated (Only 7.36% overall conversion!)
```

### Funnel Benchmarks:
* **Overall Conversion:** Only **7.4%** of SMB leads get activated.
* **Steepest Chokepoint:** Needs Assessed to Quote Accepted (only 44% conversion).
* **Cycle Time:** Average of **17.6 days** from lead generation to activation.
* **Customer Friction:** Average of **3× status chases** per customer.
* **Acquisition Cost:** Blended Customer Acquisition Cost (CAC) is **₹15,000** per activated SMB (against a median bundle price of ₹6,900/month; micro businesses average ₹2,500/month).
* **GSTIN Impact:** Leads with a GSTIN activate at **9.6%**, whereas leads without a GSTIN activate at only **2.0%**.

---

## 8. Appendix A2: Indicative Customer Segments

| Segment | Share of SMB Base | Typical Example | Current Setup | Key Needs | Price Sensitivity |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Micro Retail & Services** | 55% | Kirana, salon, pharmacy | Owner's mobile + hotspot, UPI QR | Reliable internet for UPI/POS, WhatsApp catalogue | **Very High** |
| **Professional Offices** | 25% | Clinic, CA firm, coaching centre | Home broadband, personal Gmail | High uptime, cloud email/storage, data security | **Medium** |
| **Small Multi-site Businesses** | 15% | Restaurant chain, 3–10 store retailer | Mixed ISPs per site, no central IT | Single consolidated bill, central management, CCTV, automatic failover | **Medium–Low** |
| **Small Manufacturers** | 5% | Auto-parts unit, textile unit | Leased line or local ISP | Dedicated bandwidth, IoT for machines, ERP access | **Low** |

