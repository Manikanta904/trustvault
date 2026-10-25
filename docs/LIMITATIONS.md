# TrustVault — Security Boundaries & Technical Limitations

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Auditor Principle:** Honest, evidence-based disclosure of technical boundaries, residual risks, and accepted trade-offs.

---

## 1. Implemented Safeguards vs. Deliberately Omitted Features

| Security Capability | Implementation Status in TrustVault | Architectural Rationale / Trade-Off |
|---|---|---|
| **Server-Side Authorization** | **Fully Implemented** | Live database lookup on every request (`get_authorized_document`). Client controls are never trusted. |
| **Tamper-Evident Auditing** | **Fully Implemented** | Database-level PostgreSQL triggers block `UPDATE`, `DELETE`, and `TRUNCATE` operations on `audit_logs`. |
| **Traceable PDF Watermarking** | **Fully Implemented** | Dynamic in-memory overlay with viewer name, email, UTC timestamp, and trace reference. |
| **In-Memory Permission Caching** | **Deliberately Omitted** | Caching permissions in Redis or JWTs introduces a stale authorization window. TrustVault prioritizes immediate real-time revocation over micro-optimization. |
| **Antivirus / Malware Scanning** | **Not Implemented (Deferred)** | Application validates magic bytes and incremental UTF-8 syntax. Deep antivirus scanning (e.g. ClamAV daemon) requires dedicated container infrastructure. |
| **Database Encryption at Rest** | **Not Implemented (Deferred)** | File storage and tables are cleartext on the filesystem; disk encryption (e.g. LUKS, BitLocker, AWS KMS) must be provided by the host environment. |
| **Database Hash-Chaining** | **Deliberately Omitted** | Evaluated during threat modeling; rejected in favor of PostgreSQL triggers and restricted role privileges. Software hash-chaining without external hardware HSMs adds concurrency overhead without stopping a database superuser. |

---

## 2. Inherent Physical and Technical Boundaries

### 2.1 Traceable Watermarking Limitations
- **Attribution Aid, Not Proof of Leakage:** The dynamic watermark identifies which authorized user account was used to download or view a document. It provides forensic attribution data during an investigation. However, it does not constitute legal proof that the named individual personally redistributed the document (e.g., account credential theft, shoulder surfing, or unattended workstations).
- **Physical Camera Capture & Screen Recording:** Software running in a browser or PDF engine cannot prevent physical photography of a computer monitor with a smartphone camera, hardware HDMI capture cards, or third-party operating-system screen recorders.
- **Cropping & Image Manipulation:** Although watermarks use two low-opacity diagonal placements spanning the entire page, sophisticated image editing software can partially crop or erase watermarks if only a small excerpt of text is shared.
- **No Retroactive File Erasure:** Once an authorized recipient downloads a file to their local machine, subsequent permission revocation terminates future server access but cannot remotely delete or recall files already saved to client storage.

### 2.2 Shared Non-PDF Download Policy
- **PDF-Only Dynamic Watermarking:** In-memory watermarking is implemented specifically for PDF files using `pypdf` and `reportlab`.
- **Fail-Closed Policy:** When a shared recipient attempts to download an authorized non-PDF file (such as `.txt` or `.png`), the server responds with **HTTP 422 Unprocessable Entity**:
  ```json
  {"detail": "Only PDF documents support secure watermarked downloads for shared recipients."}
  ```
  Unwatermarked files are never leaked to shared recipients. Document owners retain the ability to download original master files in all supported formats.

---

## 3. Application Architecture Limitations

### 3.1 Single-Node In-Memory Rate Limiting
- **Current Implementation:** `SlidingWindowRateLimiter` in [`app/rate_limiter.py`](file:///d:/projects/trustvault/backend/app/rate_limiter.py) maintains request timestamp history in local process memory (`defaultdict(list)`).
- **Limitation:** In a multi-worker ASGI deployment (e.g. multiple Uvicorn worker processes) or a horizontally scaled multi-container cluster, sliding windows are not shared across processes. An attacker could rotate requests across workers.
- **Production Recommendation:** Transition to a distributed Redis sliding-window limiter (e.g. Redis sorted sets).

### 3.2 Stateless JWT Token Lifespan
- **Current Implementation:** Tokens are cryptographically signed with HMAC-SHA256 and expire in 30 minutes (`JWT_EXPIRE_MINUTES=30`).
- **Limitation:** There is no server-side token revocation blacklist. If a token is compromised, it remains valid until the 30-minute expiration window closes.
- **Mitigating Factor:** Permission revocation is evaluated against live PostgreSQL records on every document access call. Revoking a user's access immediately blocks them from all document operations, even while their token remains valid.

### 3.3 Database Superuser Privilege Boundary
- **Current Implementation:** PostgreSQL triggers (`c4e1a8b29f70`) reject any `UPDATE`, `DELETE`, or `TRUNCATE` query executed against `audit_logs`.
- **Limitation:** These triggers defend against attacks originating from the application database connection (`trustvault_app`). However, a PostgreSQL superuser (`postgres`) or DBA with root server access can bypass triggers (`ALTER TABLE audit_logs DISABLE TRIGGER ALL;`) or drop the table.
- **Production Recommendation:** For enterprise regulatory compliance, replicate audit events to write-once-read-many (WORM) storage or an external immutable log sink (e.g. AWS CloudWatch / Splunk).

---

## 4. Production Deployment Status & Unverified Areas

The following items are explicitly distinguished as **locally verified** vs. **unverified in production**:

| Area | Locally Verified State | Remote Production (Render) State | Notes & Recommendations |
|---|---|---|---|
| **API Health** | Verified on localhost (`127.0.0.1:8000/health`) | **Verified** on Render (`https://trustvault-back.onrender.com/health`) | Endpoint returns `{"status":"ok"}`. |
| **Frontend Reachability**| Verified on localhost (`http://localhost:5173`) | **Verified** on Render (`https://trustvault-ui-obkw.onrender.com`) | Static site loads cleanly. |
| **CORS Origins** | Verified via test suite (`test_auth.py`) | **Partially Configured / Unverified** | `main.py` has old URL in default list; production frontend must be supplied via `CORS_ORIGINS` on Render. |
| **Persistent Storage** | Verified on local filesystem (`backend/private_storage/`) | **UNVERIFIED** | Render Web Services use ephemeral disks. Without a mounted Render Disk, uploaded files are lost on service restart. |
| **Database Triggers** | Verified via test suite (`test_audit_integrity.py`) | **UNVERIFIED** | Requires `alembic upgrade head` to have run in Render deployment build command. |
| **Production Secrets** | Verified >=32 char assertion in `app/security.py` | **UNVERIFIED** | Secret values exist only in the private Render Dashboard. |
