# TrustVault — Snovasys Hiring Challenge 2026 Submission Write-Up

**Candidate:** Manikanta Sai Anurudh  
**Project:** TrustVault — Secure Document Management with an Immutable Audit Trail  
**Live Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)  
**Live Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)  
**GitHub Repository:** `https://github.com/Manikanta904/trustvault.git`  
**Current Head Commit:** `59d7883`

---

## 1. Executive Summary & What Was Built

TrustVault was engineered from the ground up for the **Snovasys Fresher Hiring Challenge 2026** to solve a critical enterprise problem: **secure, accountable document sharing across untrusted network environments**.

Rather than implementing a superficial CRUD prototype, TrustVault was architected around **strict zero-trust boundaries**:
1. **Server-Side Authorization Truth:** Every document read, preview, download, edit, and deletion is authorized on the server against live database records. Client-side UI controls are never treated as security boundaries.
2. **Discretionary Access Control (DAC):** The document creator owns the document. Only the owner controls access grants (`read` vs `edit`). Administrators have platform oversight and audit log access, but **cannot view private document contents** without an explicit owner grant.
3. **Traceable Dynamic Watermarking:** Shared recipients download dynamically watermarked PDFs containing their full name, email, explicit UTC timestamp, document ID, and cryptographic trace reference. Stored master files remain pristine.
4. **Immediate Revocation:** Permissions are never cached in JWT tokens or memory stores. Revoking a permission row terminates access instantly on the user's next request.
5. **Tamper-Evident Forensic Audit Trail:** Mutating operations and denied access attempts are logged to PostgreSQL. Database triggers (`audit_logs_no_update_delete`, `audit_logs_no_truncate`) prevent any application-level `UPDATE`, `DELETE`, or `TRUNCATE` query.
6. **Hardened File Ingestion:** 10 MB size limit, binary magic byte verification (`%PDF-`, PNG, JPEG), incremental UTF-8 text validation with null byte rejection, and private storage under random 32-hex UUIDv4 keys.

---

## 2. The Permission Model Explained in Plain Language

TrustVault models real-world workplace access control:
- **The Owner:** When an employee uploads a contract or financial spreadsheet, they are its owner. They can update metadata, download the original file, share it with specific colleagues (`read` or `edit`), bulk share it with all active employees, or revoke access.
- **The Reader:** A colleague granted `read` access can view the document in their browser and download a watermarked PDF copy with their identity stamped across every page. They cannot edit metadata, delete the file, or share it with others.
- **The Editor:** A colleague granted `edit` access can update the document's title, description, or category in addition to viewing and downloading watermarked copies. They cannot delete the document or alter ownership.
- **The Administrator:** Responsible for compliance and monitoring. The administrator can inspect the complete audit trail, track failed logins and denied access attempts, and share documents they created. Critically, **admin role alone does not grant access to other employees' private documents**. If an administrator tries to access an unshared document, the server returns HTTP 404.

---

## 3. Deliberately Omitted Features & Engineering Justifications

1. **In-Memory Permission Caching (Redis/JWT):** Caching permissions reduces database query volume, but introduces a stale authorization window where revoked users retain access until cache expiry. TrustVault deliberately queries PostgreSQL live on every request to guarantee zero-delay immediate revocation.
2. **Database Hash-Chaining:** Evaluated during initial threat modeling; rejected in favor of PostgreSQL append-only triggers and restricted database roles (`REVOKE UPDATE, DELETE ON audit_logs`). Software hash-chaining without dedicated hardware HSMs introduces concurrency bottlenecks without preventing a database superuser from rewriting the entire chain.
3. **Deep Antivirus Scanning (ClamAV):** Application-layer ingestion validates file extensions, MIME types, magic bytes, and chunked UTF-8 encoding. True semantic malware scanning was deferred to container infrastructure rather than running heavy daemon processes inside the ASGI web server.

---

## 4. AI Tool Usage, Critical Evaluation, and Error Corrections

Development utilized AI assistance (ChatGPT GPT-4o and Antigravity IDE), accompanied by rigorous independent code review, automated test verification, and proactive defect correction:

1. **Defect 1: Token-Cached Permissions vs. Immediate Revocation**
   - *AI Output:* Proposed embedding document grants inside JWT payloads to "minimize database queries."
   - *Correction:* Rejected as a critical security flaw (revoked users would retain access for up to 30 minutes). Implemented live database queries in `app/authorization.py` ([Commit 0a3629a](https://github.com/Manikanta904/trustvault/commit/0a3629a2e4a9d4a926db095522bd0fd9f0958699)).
2. **Defect 2: Filename Path Traversal & Collisions**
   - *AI Output:* Stored files under client-supplied `original_filename`.
   - *Correction:* Replaced client filenames with server-generated random 32-hex UUIDv4 keys (`uuid4().hex`) in private storage ([Commit 0a3629a](https://github.com/Manikanta904/trustvault/commit/0a3629a2e4a9d4a926db095522bd0fd9f0958699)).
3. **Defect 3: Privilege Escalation via Registration**
   - *AI Output:* Registration schema accepted an optional `role` parameter defaulting to `owner`.
   - *Correction:* Removed `role` from schema and hardcoded `role="owner"` on the server so public clients cannot register as `admin` ([Commit 437968b](https://github.com/Manikanta904/trustvault/commit/437968b21a2ebef0d8aa6ab65f4a32904b21730c)).
4. **Defect 4: Audit Log Loss on Failed Uploads**
   - *AI Output:* Logged audit events in the main request transaction. When upload validation failed, transaction rollback silently erased the failure audit entry!
   - *Correction:* Implemented `record_upload_failure()` using an independent `SessionLocal()` so attack attempts are reliably committed ([Commit f307a68](https://github.com/Manikanta904/trustvault/commit/f307a68328e5d0082a761d346fbad6bab2f8da66)).
5. **Defect 5: Document Search Privacy Leakage**
   - *AI Output:* Filtered documents by user-supplied `owner_id` directly on the base table.
   - *Correction:* Enforced authorization join `or_(owner_id == user.id, permission.user_id == user.id)` before applying user query filters ([Commit 756884a](https://github.com/Manikanta904/trustvault/commit/756884af8ef042af6140020b8a5f4a462e9c6d07)).
6. **Defect 6: Foreign Key Cascade Breaking Deletion Under Append-Only Triggers**
   - *AI Output:* Migration `001` configured `audit_logs.document_id` with `ON DELETE SET NULL`. When an owner deleted a document, PostgreSQL executed an `UPDATE` on `audit_logs`, which the append-only trigger aborted!
   - *Correction:* Created migration `d7a2c9e4b105` dropping the foreign key constraint, allowing document deletion while retaining the original numeric document ID in historical logs ([Commit 25ca4cd](https://github.com/Manikanta904/trustvault/commit/25ca4cd4c0e64c01b17b6a4a499380f7690aa8a2)).
7. **Defect 7: Admin PDF Upload and Sharing Boundary**
   - *AI Output:* Earlier revision completely blocked administrators from uploading documents.
   - *Correction:* Permitted administrators to upload PDF documents as owner/creator while preserving strict isolation between distinct users ([Commit 59d7883](https://github.com/Manikanta904/trustvault/commit/59d7883210bf5666749f39d5112bebee96e72a48)).

---

## 5. Quantitative Verification & Quality Metrics

- **Backend Automated Test Suite:** **135 passed tests across 12 test files** (`pytest` in 35.15s).
- **Frontend Type Safety:** `npm run build` (`tsc -b && vite build`) passes with **0 errors**.
- **Frontend Code Quality:** `npm run lint` (`eslint .`) passes with **0 errors and 0 warnings**.
- **Git Repository Hygiene:** Zero tracked `.env` files, zero tracked SQLite files, and zero tracked database dumps.

---

## 6. Unfinished Work & Production Recommendations

1. **Render Persistent Disk Mount:** Render free web services use ephemeral container storage. While local file storage is verified, deploying to production requires attaching a persistent Render Disk to preserve uploaded files across restarts.
2. **Distributed Rate Limiting:** Replace process-local in-memory sliding windows with Redis sorted sets when scaling across multiple container instances.
3. **Production CORS Setting:** Ensure `CORS_ORIGINS=https://trustvault-ui-obkw.onrender.com` is set in the Render backend dashboard.
