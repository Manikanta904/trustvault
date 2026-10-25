# TrustVault — Security Testing & Verification Report

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Test Suite Metric:** **135 Passed Tests Across 12 Test Files (0 Failures)**  
**Execution Runtime:** ~35 seconds on local PostgreSQL test database (`trustvault_test`)

---

## 1. Test Suite Architecture & Environment Isolation

TrustVault enforces strict separation between development and testing environments:
- **Test Database Isolation:** Managed by `backend/tests/conftest.py`. Tests connect exclusively to `DATABASE_URL_TEST` (targeting `trustvault_test`). Running the test suite never contaminates or mutates the development database.
- **Automatic Migration Setup:** `conftest.py` runs `alembic upgrade head` before test execution, ensuring all tables, foreign keys, and PostgreSQL PL/pgSQL triggers (`c4e1a8b29f70`) are active.
- **Transactional Clean-Up:** Test fixtures create isolated users and documents, cleaning up entities without violating append-only triggers.

### Execution Commands

```bash
cd backend

# 1. Run complete automated regression suite (all 135 tests):
.venv\Scripts\pytest.exe -v

# 2. Run quiet summary check:
.venv\Scripts\pytest.exe -q

# 3. Run individual security test suites:
.venv\Scripts\pytest.exe tests/test_authorization.py
.venv\Scripts\pytest.exe tests/test_phase4_watermark_and_downloads.py
.venv\Scripts\pytest.exe tests/test_audit_integrity.py
.venv\Scripts\pytest.exe tests/test_admin_upload_and_sharing.py
```

---

## 2. Test File Breakdown and Security Scenarios Covered

```
tests/test_admin_api.py .................                                [ 12%]
tests/test_admin_upload_and_sharing.py ......                            [ 17%]
tests/test_audit_integrity.py ...                                        [ 19%]
tests/test_auth.py ............                                          [ 28%]
tests/test_authorization.py .......                                      [ 33%]
tests/test_documents_api.py ...............................              [ 56%]
tests/test_file_storage.py .......                                       [ 61%]
tests/test_phase1_security.py .........                                  [ 68%]
tests/test_phase2_backend_features.py ....                               [ 71%]
tests/test_phase2_user_search_and_sharing.py .........                   [ 77%]
tests/test_phase4_watermark_and_downloads.py ..................          [ 90%]
tests/test_registration.py ............                                  [100%]

============================== 135 passed in 35.15s ==============================
```

### 1. `tests/test_auth.py` (12 Tests) — Authentication & Token Security
- **Token Validity:** Verifies standard JWT lifecycle (`login` -> token -> `/auth/me`).
- **Claim Assertions:** Rejects tokens missing `sub` or `exp` claims; rejects expired tokens.
- **Signature Integrity:** Rejects tokens signed with wrong secret or tampered payloads.
- **Account State Verification:** Asserts deactivated accounts (`is_active=False`) are rejected at login and blocked when presenting previously issued tokens.
- **CORS Handling:** Validates CORS preflight OPTIONS headers.

### 2. `tests/test_registration.py` (12 Tests) — Registration & Privilege Escalation
- **Role Elevation Defense:** `test_client_cannot_register_as_admin` verifies that sending `{"role": "admin"}` in the registration payload is ignored; the user is stored as `owner`.
- **Password Complexity:** 8 parameterized tests verifying rejection of: short passwords (<8 chars), missing uppercase letters, missing lowercase letters, missing digits, and missing special characters.
- **Email Normalization:** Trims whitespace and lowercases emails; rejects duplicates with HTTP 409 Conflict.

### 3. `tests/test_authorization.py` (7 Tests) — Core Authorization Engine Unit Tests
- **Owner Rights:** Asserts document owner has implicit read and edit permissions.
- **Ungranted Users:** Asserts users without a grant receive HTTP 404.
- **Read vs. Edit:** Asserts `read` grant permits read/download but rejects `edit` (404); asserts `edit` grant permits read and edit.
- **Admin Isolation:** Asserts platform administrator without explicit grant receives HTTP 404 when querying document API.
- **Immediate Revocation:** Asserts deleting permission row immediately blocks subsequent access.

### 4. `tests/test_documents_api.py` (31 Tests) — Document Lifecycle & Transactional Integrity
- **Authentication Requirement:** Asserts all document routes return HTTP 401 if unauthenticated.
- **Cross-User Isolation:** Asserts Owner A cannot read, edit, download, or delete Owner B's document.
- **Audit-Write Atomicity:** Asserts that if an audit log write fails, document updates, permission grants, revocations, and deletions are rolled back.
- **Download Protection on Audit Failure:** Asserts file transmission is aborted if audit recording fails.
- **Failed Upload Persistence:** Verifies rejected uploads (`malicious.exe`) are committed to `audit_logs` independently.
- **Preserved Audit References on Deletion:** Asserts document deletion retains the original `document_id` in historical audit records.
- **Search Scoping:** Asserts keyword, category, and date search never expose unshared documents.
- **Owner Self-Grant Denial:** Asserts document owner cannot grant permissions to self (HTTP 400).
- **Pagination Safety:** Asserts bounded limit (1–100) and offset on document listings.

### 5. `tests/test_admin_api.py` (17 Tests) — Audit Log Governance
- **Role Enforcement:** Asserts non-admin users receive HTTP 403 when requesting `/admin/audit-logs`.
- **Denial Auditing:** Asserts unauthorized access attempts to audit logs create a denial audit entry.
- **Filtering & Pagination:** Validates filtering by action, outcome, actor ID, document ID, start date, and end date; validates upper-bound pagination limits.

### 6. `tests/test_audit_integrity.py` (3 Tests) — Database Trigger Immutability
- **Trigger Tests:** Directly attempts raw SQL queries against PostgreSQL `audit_logs`:
  - `UPDATE audit_logs SET details = ...`: Aborted by trigger `audit_logs_no_update_delete`.
  - `DELETE FROM audit_logs WHERE id = ...`: Aborted by trigger `audit_logs_no_update_delete`.
  - `TRUNCATE audit_logs`: Aborted by trigger `audit_logs_no_truncate`.

### 7. `tests/test_file_storage.py` (7 Tests) — File Ingestion & Parsing Hardening
- **Signature & Header Validation:** Rejects files with spoofed extensions or invalid magic bytes (invalid PDF signature, `.exe` upload).
- **Size Limits:** Rejects uploads exceeding 10 MB with HTTP 413.
- **Incremental UTF-8 Decoding:** Validates text streaming across 64 KB chunk boundaries; rejects null bytes (`\x00`) and malformed multibyte UTF-8 sequences.
- **Zero-Byte Files:** Rejects empty 0-byte file uploads with HTTP 415.

### 8. `tests/test_phase1_security.py` (9 Tests) — Integration Security Matrix
- Comprehensive end-to-end integration tests verifying IDOR prevention, URL tampering immunity, token expiration rejection, immediate permission revocation lifecycle, and audit trail completeness.

### 9. `tests/test_phase2_backend_features.py` (4 Tests) — Streaming & Bulk Sharing
- Verifies secure in-browser streaming headers (`X-Frame-Options`, `Content-Security-Policy: frame-ancestors 'self'`, `Cache-Control: private, no-store`).
- Verifies bulk sharing lifecycle and atomic rollback if a grant fails during bulk processing.

### 10. `tests/test_phase2_user_search_and_sharing.py` (9 Tests) — Directory Privacy
- Verifies employee search excludes caller (`id != user.id`); excludes inactive users; returns minimal fields (no password hashes); verifies grant and revoke lifecycle.

### 11. `tests/test_phase4_watermark_and_downloads.py` (18 Tests) — Dynamic Watermarking & Download Policy
- **Owner vs. Viewer Download:** Owner receives unwatermarked master file; shared viewers receive watermarked copy.
- **Disk Invariance:** Master PDF checksum on disk remains bit-for-bit identical after watermarked downloads.
- **Watermark Content Verification:** Asserts generated PDF text contains viewer's email, viewer's name, UTC timestamp, and trace reference.
- **Multi-Page Coverage:** Asserts every page of a multi-page PDF is stamped.
- **Viewer-Specific Generation:** Asserts User A and User B receive distinctly stamped watermarked copies.
- **Owner Activity Visibility:** Asserts owner can inspect recipient download activity at `GET /documents/{id}/activity`.
- **Fail-Closed Verification:** Asserts corrupt or non-PDF shared downloads fail closed with HTTP 422.
- **Rate Limiting:** Asserts sliding-window limiter blocks excessive downloads with HTTP 429.

### 12. `tests/test_admin_upload_and_sharing.py` (6 Tests) — Admin PDF Upload & Sharing
- Added in commit `59d7883`: verifies administrators can upload PDF documents as creator/owner, list them, download original unwatermarked copies, grant permissions to viewers, verifies shared viewer receives a watermarked copy of the admin's document, and verifies admin deletion removes document and revokes viewer access.

---

## 3. Separation of Automated vs. Production Verification

| Verification Level | Execution Scope | Verification Status |
|---|---|---|
| **Automated Backend Tests** | 135 pytest test cases executed locally against PostgreSQL `trustvault_test` | **100% Passed (135/135)** |
| **Frontend TypeScript Build** | `npm run build` (`tsc -b && vite build`) executed in `frontend/` | **Passed (0 Errors)** |
| **Frontend ESLint Check** | `npm run lint` (`eslint .`) executed in `frontend/` | **Passed (0 Errors, 0 Warnings)** |
| **Production Health Check** | `GET https://trustvault-back.onrender.com/health` via network request | **Verified Reachable (`{"status":"ok"}`)** |
| **Production Frontend Reachability**| `GET https://trustvault-ui-obkw.onrender.com` via network request | **Verified Reachable (HTTP 200)** |
| **Production DB Triggers & Storage**| Direct SQL inspection of remote Render PostgreSQL instance | **UNVERIFIED (Requires remote DB credentials)** |
