# Accel SYNC — Data Privacy & DPDP Act 2023 Compliance Note

> **Platform:** Accel SYNC | Airtel Business MSME Onboarding Platform
> **Document Type:** Privacy & Compliance Reference (Internal + Customer-Facing Summary)
> **Applicable Law:** Digital Personal Data Protection Act, 2023 (DPDP Act)
> **Data Fiduciary:** Bharti Airtel Limited (acting through Accel SYNC platform)
> **Data Protection Officer:** dpo@accelsync.in
> **Last Reviewed:** November 2026 | **Next Review Due:** May 2027

---

> [!IMPORTANT]
> This document constitutes Accel SYNC's formal compliance reference under the DPDP Act 2023. All engineering, product, and operations team members must be familiar with its contents. Any proposed feature that involves collection, processing, or storage of personal data must be reviewed against this document before implementation.

---

## 1. Data We Collect & Why (Purpose Limitation)

Accel SYNC collects the **minimum data necessary** to deliver business connectivity services to MSME customers. No data is collected speculatively, for profiling, or for any purpose not explicitly listed below.

| Data Element | Collected At | Purpose | Stored? | Retention Period | Legal Basis |
|---|---|---|---|---|---|
| Business name, type, city | AI Advisor chat (Module 1) | Bundle recommendation only; not linked to identity | **No — session only** | Deleted when session ends (browser memory) | Legitimate interest (service delivery) |
| GSTIN number | KYC Step 2 | Identity verification via GST registry | **Yes, encrypted** | 7 years (GST Act 2017 requirement) | Legal obligation |
| Udyam number | KYC Step 2 | MSME eligibility verification | **Yes, encrypted** | 7 years | Legal obligation |
| GST certificate image | KYC Step 3 (upload) | OCR field extraction + cross-verification only | **Yes, encrypted** | **90 days then auto-deleted** | Consent (explicit) |
| Udyam certificate image | KYC Step 3 (upload) | OCR field extraction + cross-verification only | **Yes, encrypted** | **90 days then auto-deleted** | Consent (explicit) |
| Authorised signatory ID | KYC Step 3 (upload) | Signatory verification only; full number masked in logs | **Yes, encrypted; masked in logs** | **90 days then auto-deleted** | Consent (explicit) |
| Address proof document | KYC Step 3 (upload) | Address verification | **Yes, encrypted** | **90 days then auto-deleted** | Consent (explicit) |
| Mobile number | Order creation (Module 4) | Order tracking + customer support contact | **Yes** | Contract period + 1 year post-termination | Contract necessity |
| Order details (bundle, pricing) | Order creation | Service delivery + billing | **Yes** | Contract period + 3 years | Contract necessity + legal obligation |
| Consent action log | Each consent checkpoint | Audit trail of consent given/withdrawn | **Yes, pseudonymised** | 3 years from last interaction | DPDP Act Section 7 obligation |
| AI chat transcript | AI Advisor session | Session context for multi-turn conversation | **No — never persisted** | Cleared when session ends | N/A (not stored) |

> [!NOTE]
> **What we explicitly do NOT collect:**
> - Full Aadhaar number (last 4 digits only, if visible on uploaded documents)
> - PAN number standalone (masked when embedded in GSTIN; never stored separately)
> - Financial account details (bank account, UPI ID)
> - Biometric data
> - Location data beyond city (self-declared)
> - Browsing history or cross-site tracking identifiers

---

## 2. Consent Architecture

Accel SYNC's consent framework is designed to meet and exceed DPDP Act 2023 Section 6 requirements. Consent is **freely given, specific, informed, unconditional, and unambiguous** at every collection point.

### 2.1 Consent Checkpoints in the Journey

| Step | Consent Item | Type | Consequence if Declined |
|---|---|---|---|
| AI Advisor start | Use of session data for bundle recommendation | **Required** | Cannot use AI Advisor (use static bundle catalogue instead) |
| KYC Step 2 | GSTIN/Udyam lookup in government registries | **Required** | Cannot complete digital KYC |
| KYC Step 3 | Document upload and OCR processing | **Required** | Cannot complete digital KYC |
| KYC Step 3 | Document retention for 90 days | **Required** | Cannot proceed (compliance requirement) |
| Order creation | SMS/WhatsApp order status notifications | **Required** | Cannot use Order Tracker |
| Order creation | Airtel Business promotional communications | **Optional** | No impact on service delivery |
| Order creation | Sharing anonymised usage data to improve AI Advisor | **Optional** | No impact on service delivery |

### 2.2 Consent Implementation Standards

- **No dark patterns:** Required and optional consent items are visually differentiated — required items use a lock icon (🔒), optional items use a star icon (⭐). Pre-ticked checkboxes are prohibited.
- **Bundling prohibited:** KYC consent is never bundled with marketing consent on the same checkbox.
- **Plain language:** All consent text written at ≤ 8th grade reading level, available in English and Hindi in Phase 1.
- **Withdrawable:** Optional consents can be withdrawn at any time via the endpoint `POST /api/consent/withdraw` or by emailing grievance@accelsync.in.
- **Logged immutably:** Every consent action (given, withdrawn, re-given) is written to `consent_logs` table with:
  - ISO-8601 UTC timestamp
  - Consent item identifier
  - Action (GIVEN / WITHDRAWN)
  - SHA-256 hash of the requesting IP (not raw IP)
  - User agent string
  - Customer pseudonymous ID

### 2.3 Consent API Reference

| Action | Endpoint | Method | Auth Required |
|---|---|---|---|
| Record consent | `/api/consent/record` | POST | OTP-verified session |
| Withdraw optional consent | `/api/consent/withdraw` | POST | OTP-verified session |
| Check current consent status | `/api/consent/status` | GET | OTP-verified session |
| Retrieve consent history | `/api/consent/history` | GET | OTP-verified session |

---

## 3. Data Minimization

> [!TIP]
> Data minimization is enforced at the **code level**, not just policy level. Each of the following practices is implemented in the FastAPI backend and cannot be bypassed without a code change.

### 3.1 OCR Data Minimization

pytesseract OCR is configured to extract **exactly five fields** per document type:

| Document | Fields Extracted by OCR |
|---|---|
| GST Certificate | GSTIN, Legal Business Name, State, Registration Date, Status |
| Udyam Certificate | Udyam Number, Enterprise Name, Category (Micro/Small/Medium), NIC Activity |
| Signatory ID | Name, Document Type, Document Number (masked), Issue Date, Expiry Date |
| Address Proof | Name, Address Line 1, City, PIN Code, State |

**After OCR extraction:**
1. Raw image bytes are **immediately discarded from memory** (`del image_bytes; gc.collect()`)
2. Only the five extracted text fields are passed to the validation layer
3. The encrypted file is saved to storage **separately** and **not** accessible to the OCR layer after the initial call

### 3.2 Sensitive Identifier Masking

| Identifier | Masking Rule | Example |
|---|---|---|
| PAN (embedded in GSTIN chars 3–12) | Replaced with `XXXXXXXXXX` in all logs and API responses | `22XXXXXXXXX1Z5` |
| Aadhaar number | Last 4 digits only displayed; full number never stored; `XXXX-XXXX-` prefix prepended | `XXXX-XXXX-6789` |
| Mobile number | Last 4 digits visible in UI; full number stored encrypted; masked in all logs | `XXXXXX7890` |
| Signatory ID number | First 2 + last 2 characters visible; rest masked | `AB**....**YZ` |

### 3.3 AI Advisor Data Minimization

The Gemini API receives **only the customer's conversational text**. Before any message is sent to Gemini:
- A regex scrubber strips patterns matching GSTIN, Aadhaar, PAN, and mobile numbers
- The system prompt explicitly instructs Gemini not to request or repeat personal identifiers
- No conversation history is persisted beyond the browser session

---

## 4. Security Controls

### 4.1 Encryption

| Layer | Standard | Implementation |
|---|---|---|
| Documents at rest | AES-256 | Python `cryptography.fernet` (256-bit key); key stored in environment variable, not in codebase |
| Database sensitive fields | Application-level field encryption | GSTIN, Udyam number, mobile number encrypted before INSERT; decrypted only when needed for display |
| Data in transit | TLS 1.3 | Enforced at reverse proxy layer (Nginx) in production; HTTP → HTTPS redirect mandatory |
| Encryption key management | Environment variable (hackathon) | Production: Google Cloud Secret Manager / AWS Secrets Manager with rotation policy |

### 4.2 Document Access Control

KYC documents stored in the file system (hackathon) or Cloud Storage (production) are **never served via direct file paths or public URLs**.

- Access requires a **signed, time-limited token** generated by `/api/kyc/document-url`
- Tokens expire after **15 minutes**
- Each token is single-use (invalidated after first access)
- Document access events are logged with customer ID, timestamp, and accessing user role

### 4.3 API Security

| Control | Implementation |
|---|---|
| Authentication | JWT (HS256), 1-hour expiry; refresh token with 7-day TTL |
| Initial login | Mobile OTP via Airtel SMS gateway; 6-digit, 5-minute expiry, 3-attempt lockout |
| Rate limiting | 100 requests/minute per IP for public endpoints; 1,000/minute for authenticated |
| Input validation | Pydantic models enforce type, length, and format constraints on all inputs |
| SQL injection | SQLAlchemy ORM with parameterised queries; raw SQL prohibited |
| File upload | Type allowlist (JPEG, PNG, PDF only); max 5 MB; antivirus scan in production |
| CORS | Strict allowlist of frontend origins; wildcard `*` prohibited |

### 4.4 Logging & Monitoring

| Log Type | What Is Logged | What Is NOT Logged |
|---|---|---|
| API access logs | Endpoint, method, status code, latency, pseudonymous user ID | Full request body, mobile number, document content |
| KYC events | KYC status change, timestamp, pseudonymous customer ID | Extracted document field values |
| Consent events | Action, item, timestamp, IP hash | Full IP address, raw consent text |
| OCR events | Document type, fields detected (count only), confidence score | Actual extracted text values |
| Error logs | Stack trace, endpoint, error type | Personal data values in any form |

---

## 5. Data Principal Rights (DPDP Act Sections 11–13)

Every customer whose data is processed by Accel SYNC is a **Data Principal** under the DPDP Act and holds the following rights, all implemented as working API endpoints.

| Right | DPDP Act Section | How Accel SYNC Implements It | SLA |
|---|---|---|---|
| **Right to Access** | Section 11 | `GET /api/my-data/{mobile}` — returns all data fields stored against the mobile number in a structured JSON response | Immediate (automated) |
| **Right to Correction** | Section 12 | `PATCH /api/my-data/{mobile}` — allows customers to correct business name, address, and contact details; each correction is logged with reason | 24 hours for processing |
| **Right to Erasure** | Section 12 | `DELETE /api/my-data/{mobile}` — hard-deletes all personal data **except** legally mandated retention (GSTIN/Udyam records retained 7 years per GST Act; KYC status retained for regulatory audit trail) | 72 hours for processing |
| **Right to Grievance Redressal** | Section 13 | `grievance@accelsync.in` — dedicated grievance email; acknowledgement within 48 hours; resolution within **30 days** | 30-day resolution SLA |
| **Right to Nominate** | Section 14 | Nominee designation for account management in case of death/incapacity — **roadmap feature, Phase 2** | Phase 2 |

> [!WARNING]
> Erasure requests cannot remove data subject to a legal hold or regulatory retention requirement. When a partial erasure occurs (some data retained due to legal obligation), the customer will receive a written explanation specifying exactly which data is retained, under which law, and for how long.

### Exercising Rights Without the API

Customers who cannot or prefer not to use the self-service API may exercise any right by:
1. Emailing `grievance@accelsync.in` with subject line `DATA RIGHT REQUEST — [Right Name]`
2. Calling Airtel Business customer care and requesting escalation to the DPDP team
3. Submitting a request at any Airtel Business relationship centre

---

## 6. Data Fiduciary Obligations

As the **Data Fiduciary**, Bharti Airtel Limited (Accel SYNC) bears full responsibility for the lawful processing of all personal data on the platform, including data processed by sub-processors.

### 6.1 Sub-Processor Register

| Sub-Processor | Service | Data Shared | Safeguard | DPA in Place? |
|---|---|---|---|---|
| **Google LLC (Gemini API)** | AI Advisor language model | Scrubbed chat text (no PII) | Google Cloud DPA; no training on user data; `safetySettings` configured | ✅ Yes |
| **Tesseract / pytesseract** | Document OCR | Image bytes (in-memory only, never egressed) | Runs entirely on-premise; zero network calls; open-source, auditable | N/A (on-premise tool) |
| **Google Cloud Platform** (production) | Infrastructure, storage | Encrypted data at rest | Cloud DPA; data residency: India region (asia-south1) | ✅ Yes |
| **Airtel SMS Gateway** | OTP delivery | Mobile number (for OTP sending only) | Internal Airtel system; number not retained by SMS system after delivery | Internal |

> [!CAUTION]
> **No third-party analytics, advertising, or tracking SDKs are embedded on any KYC-related page.** This is a hard engineering constraint enforced via Content Security Policy headers. Adding any such SDK requires DPDP team sign-off.

### 6.2 Governance Controls

| Control | Frequency | Responsible Party |
|---|---|---|
| External DPDP compliance audit | Annual | External auditor (empanelled firm) |
| Internal privacy review of new features | Per feature sprint | Data Protection Officer |
| Encryption key rotation | Every 6 months | Platform Security team |
| Sub-processor DPA review | Annual | Legal team |
| Consent framework review | Annual or on DPDP Act amendment | Legal + Product team |
| Data breach simulation drill | Bi-annual | Security + Engineering |

### 6.3 Data Breach Response

In the event of a confirmed personal data breach:
1. **Within 72 hours:** Notify the Data Protection Board of India (once constituted) as required by DPDP Act
2. **Within 72 hours:** Notify all affected Data Principals via SMS and email
3. Breach notification will include: nature of breach, data categories affected, likely consequences, remedial measures taken
4. A post-incident report will be published internally within 30 days

---

## 7. Children's Data

> [!IMPORTANT]
> **Accel SYNC does not knowingly collect personal data of individuals under the age of 18.**

The platform is restricted to business owners and authorised business representatives. The following age verification controls are in place:

1. **Terms of Service** explicitly state the platform is for use by individuals aged 18 and above who are authorised to represent a legal business entity.
2. **Mobile OTP verification** at account creation acts as a functional age gate — mobile connections in India require Aadhaar-linked KYC under TRAI regulations, which establishes the subscriber is an adult.
3. **Business entity requirement:** All users must provide a valid GSTIN or Udyam number, both of which are issued only to legally registered businesses with adult-identified proprietors/directors.

If Accel SYNC identifies that personal data of a minor has been collected, it will immediately delete that data and invalidate the associated account without prior notice.

---

## 8. Contact Information

| Role | Contact | Availability |
|---|---|---|
| **Data Protection Officer** | dpo@accelsync.in | Business hours (Mon–Fri, 10am–6pm IST) |
| **Grievance Officer** | grievance@accelsync.in | 48-hour acknowledgement SLA |
| **Platform Security** | security@accelsync.in | 24×7 for breach reports |
| **Customer Care (DPDP Rights)** | 1800-XXX-XXXX (Airtel Business) | 8am–10pm IST, 7 days |

---

*This document is reviewed and approved by the Accel SYNC Data Protection Officer. It is effective from the date of platform launch and supersedes all prior privacy documentation for this platform.*

*Accel SYNC © 2026 Bharti Airtel Limited. All rights reserved.*
