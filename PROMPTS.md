# TrustVault — AI Development Log

This log records AI-assisted development, critical evaluation, error correction, and verification for TrustVault (Snovasys Fresher Hiring Challenge 2026). Each entry documents the prompt/request, the AI output, the specific defects or security weaknesses identified, the corrective actions taken, links to real repository commits, and the concrete verification performed.

---

## Shared Instructions and Reused Context Files

The following context files and standard instructions were reused across development sessions:
- **Challenge Requirements & Security Guidelines:** Specifying administrator, owner, and viewer roles, per-document permissions, server-side authorization on every route, append-only audit trail, upload validation, immediate revocation, and honest documentation of security boundaries.
- **Backend Architecture & Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL with `psycopg`, Alembic, Argon2id (`pwdlib`), PyJWT (`HS256`), and private filesystem storage.
- **Database Safety Guard:** Strict separation between development (`trustvault`) and test (`trustvault_test`) databases; never run tests against development data.
- **Repository Hygiene Rule:** Never commit secrets, `.env`, virtual environments, SQLite files, uploaded private files, or database dumps.

---

## Entry 1 — 2026-10-19 — Backend foundation, authentication, and role enforcement

- **AI tools used:** ChatGPT (GPT-4o); VS Code for code inspection and execution.
- **Objective:** Establish the initial FastAPI backend with user authentication, role differentiation (`admin`, `owner`, `viewer`), Argon2 password hashing, JWT creation, login/me endpoints, demo seeding, and pytest tests.
- **Prompt / request (summary):** Asked the AI to design and generate a FastAPI backend project structure with SQLAlchemy models, secure password hashing using Argon2, JWT token generation with expiration, OAuth2 password request login, `/auth/me`, demo account seeding, and automated authentication tests.
- **AI output / implementation:** The AI provided `app/database.py`, `app/models.py`, `app/security.py`, `app/main.py`, `seed_demo.py`, and `tests/test_auth.py`.
- **What was specifically wrong with the output or approach:**
  1. The AI initially configured SQLite (`sqlite:///./trustvault.db`) for local development rather than PostgreSQL, which obscured database-specific concurrency, trigger, and constraint behaviors.
  2. The tests ran directly against the development database, meaning running tests would contaminate or wipe development data.
  3. The initial JWT validation decoded the token without explicitly verifying the required presence of both `sub` (subject) and `exp` (expiration) claims, allowing malformed tokens without expiration to pass.
  4. The generated `seed_demo.py` script used `Base.metadata.create_all()` which bypassed migration tracking.
- **Correction / what I did instead:**
  1. Hardened JWT decoding in `app/security.py` with `options={"require": ["sub", "exp"]}` and explicit algorithm pinning (`algorithms=["HS256"]`).
  2. Replaced the SQLite configuration with PostgreSQL using `psycopg` and established the Alembic migration framework (`migrations/versions/fa9d3cc8788d_create_users_table.py`) to enforce reproducible schema versions.
  3. Identified the database isolation defect and planned dedicated test database configuration (later isolated in `conftest.py`).
- **Commit links:**
  - Initial authentication milestone: [Commit a77ba13](https://github.com/Manikanta904/trustvault/commit/a77ba13e10c7a7de795aced5153f3e2c02545319)
  - PostgreSQL and Alembic migration configuration: [Commit 3493193](https://github.com/Manikanta904/trustvault/commit/3493193959153204564dcb5734f816311232ce0a)
- **Verification performed:**
  - Started the Uvicorn server on `127.0.0.1:8000` and confirmed OpenAPI/Swagger docs loaded cleanly.
  - Executed `python -m pytest tests/test_auth.py -v`: **5 passed in 1.45s** (health check, unauthenticated `/auth/me` rejection, successful login, invalid password rejection, and unknown user rejection).

---

## Entry 2 — 2026-10-19 — Document authorization, private storage, and API testing

- **AI tools used:** ChatGPT (GPT-4o); VS Code and PowerShell terminal.
- **Objective:** Extend the backend with document models, per-document read/edit permissions, private file storage, permission grant/revocation, audit logging, and automated authorization tests.
- **Prompt / request (summary):** Requested implementation of document management routes (`/documents`), private file storage utilities with extension and size checks, an authorization helper to check read vs. edit access, an audit logger, and comprehensive tests verifying cross-user isolation and immediate revocation.
- **AI output / implementation:** Provided `app/routers/documents.py`, `app/authorization.py`, `app/audit.py`, `app/file_storage.py`, schemas, and tests in `tests/test_authorization.py` and `tests/test_documents_api.py`.
- **What was specifically wrong or incomplete (and what was independently checked):**
  1. **Token-cached permissions vs. Immediate Revocation:** The AI proposed caching permission checks inside the JWT access token payload to "reduce database queries." This was a severe architectural security flaw: if an owner revoked a user's access, the user would retain access until their JWT expired (up to 30 minutes), violating the mandatory Immediate Revocation standard.
  2. **Filename path traversal and collisions:** The file upload implementation originally stored files under client-provided filenames (`original_filename`), creating directory traversal risks (`../../etc/passwd`) and filename collisions across users uploading files with the same name.
  3. **Information leakage via HTTP 403:** The authorization checks initially returned HTTP 403 Forbidden for inaccessible documents. This leaked information by allowing an attacker to determine whether another user's private document ID existed (document existence enumeration).
  4. **Administrator role boundary (independently evaluated):** The AI's initial draft assumed administrators should have global override to view all documents. I independently checked this against the zero-trust requirements and determined that administrators must NOT automatically access document content without an explicit owner grant.
- **Correction / what I did instead:**
  1. Rejected JWT-cached permissions. Implemented `get_authorized_document()` in `app/authorization.py` to query the live `document_permissions` table on every single request, guaranteeing that permission revocation takes effect instantly.
  2. Enforced random server-generated 32-hex UUIDv4 storage keys (`uuid.uuid4().hex`) in `app/file_storage.py`. The client-supplied filename is stored strictly as sanitized metadata in the database.
  3. Replaced HTTP 403 with HTTP 404 Not Found for ungranted document access, preventing document existence enumeration.
  4. Enforced strict zero-trust administrator boundaries: an administrator without an explicit grant receives HTTP 404 when attempting to access or download document content.
- **Commit link:** [Commit 0a3629a](https://github.com/Manikanta904/trustvault/commit/0a3629a2e4a9d4a926db095522bd0fd9f0958699)
- **Verification performed:**
  - Unit tests in `tests/test_authorization.py`: **7 passed** (`test_owner_can_read_and_edit_own_document`, `test_user_without_grant_cannot_access_document`, `test_read_grant_allows_read_but_denies_edit`, `test_edit_grant_allows_read_and_edit`, `test_admin_without_grant_cannot_access_document`, `test_revoked_permission_blocks_next_access`, `test_missing_document_returns_404`).
  - Integration tests in `tests/test_documents_api.py`: verified upload, download, permission grant, and immediate revocation over HTTP.
  - Automated suite: `python -m pytest -v`: **17 passed, 1 warning in 3.80s**.

---

## Entry 3 — 2026-10-19 — Secure user registration and privilege escalation prevention

- **AI tools used:** ChatGPT (GPT-4o); VS Code and terminal.
- **Objective:** Implement a public self-registration endpoint (`POST /auth/register`) while preventing privilege escalation and account enumeration.
- **Prompt / request (summary):** Asked the AI to create a registration endpoint accepting name, email, and password, validating input formats, hashing passwords with Argon2, and returning user details.
- **AI output / implementation:** Provided `POST /auth/register` in `app/main.py` and `UserRegister` schema in `app/schemas.py`.
- **What was specifically wrong with the output or approach:**
  1. The schema accepted an optional `role` parameter from the client, defaulting to `owner`. An attacker could send `{"role": "admin"}` in the registration JSON to self-assign administrative privileges, causing a catastrophic privilege escalation flaw.
  2. Email addresses were not normalized (no stripping of whitespace or lowercasing), allowing duplicate accounts like `Alice@example.com` and `alice@example.com` to bypass uniqueness constraints or cause login confusion.
  3. Name validation accepted whitespace-only strings (e.g. `"   "`).
- **Correction / what I did instead:**
  1. Completely removed the `role` field from the `UserRegister` schema. Hardcoded `role="owner"` inside the server-side endpoint handler so that public clients can never self-assign the `admin` role.
  2. Added Pydantic field validators in `app/schemas.py` using `EmailStr` and `@field_validator` to strip and lowercase email addresses and reject blank/whitespace names.
  3. Added explicit database duplicate-email conflict handling returning HTTP 409 Conflict.
- **Commit link:** [Commit 437968b](https://github.com/Manikanta904/trustvault/commit/437968b21a2ebef0d8aa6ab65f4a32904b21730c)
- **Verification performed:**
  - Executed `python -m pytest tests/test_registration.py -v`: **7 passed in 1.12s**.
  - Verified test `test_client_cannot_register_as_admin` passes and proves that even if `role: "admin"` is sent in the payload, the stored user role remains `owner`.
  - Full suite run: **24 passed, 1 warning in 4.10s**.

---

## Entry 4 — 2026-10-20 — Administrative audit API, audit completeness, and failure audit persistence

- **AI tools used:** ChatGPT (GPT-4o); VS Code and PowerShell terminal.
- **Objective:** Implement the administrator audit API (`GET /admin/audit-logs`) with query filters and pagination, and ensure security-sensitive failures and denied operations are audited.
- **Prompt / request (summary):** Asked to build an admin-only endpoint to inspect audit events, add filters for action, outcome, actor ID, and date ranges, and ensure rejected operations are audited.
- **AI output / implementation:** Provided `app/routers/admin.py` with `GET /admin/audit-logs` and added audit calls to `app/routers/documents.py`.
- **What was specifically wrong or incomplete (and what was independently checked):**
  1. **Upload failure audit rollback defect:** The AI originally attempted to record audit logs inside the same request transaction as the upload. When an upload failed validation (unsupported extension, bad signature, or oversized payload), FastAPI rolled back the database transaction (`db.rollback()`), which silently erased the audit record! Consequently, rejected attacks were completely absent from the audit trail.
  2. **Unbounded pagination DoS risk:** The AI omitted upper bounds on the `limit` query parameter, allowing an administrator (or compromised admin token) to query `?limit=1000000`, causing PostgreSQL table scans and memory exhaustion.
  3. **Role enforcement verification:** Independently inspected the endpoint dependencies and verified that only callers with `user.role == "admin"` can access audit logs; unauthenticated callers receive HTTP 401 and non-admins receive HTTP 403.
- **Correction / what I did instead:**
  1. Implemented `record_upload_failure()` in `app/routers/documents.py` using an independent database session context (`with SessionLocal() as audit_db:`) so that upload validation failures and rejections are reliably committed to PostgreSQL even when the primary upload transaction is aborted.
  2. Enforced bounded pagination using FastAPI `Query(default=50, ge=1, le=100)` and `offset >= 0` with deterministic ordering `order_by(AuditLog.created_at.desc(), AuditLog.id.desc())`.
  3. Guarded the endpoint with `user.role != "admin"` check returning HTTP 403 Forbidden.
- **Commit link:** [Commit f307a68](https://github.com/Manikanta904/trustvault/commit/f307a68328e5d0082a761d346fbad6bab2f8da66)
- **Verification performed:**
  - Swagger UI: verified unauthenticated request returned 401, owner returned 403, and admin returned 200.
  - Executed `python -m pytest tests/test_admin_api.py -v`: **10 passed in 2.85s**.
  - Verified `test_failed_upload_is_recorded_in_audit_log` in `tests/test_documents_api.py`: uploaded `malicious.exe`, confirmed HTTP rejection (400/415/422), and queried PostgreSQL `audit_logs` table directly to verify the `action="document_upload", outcome="failure"` record was stored.
  - Full suite run: **34 passed, 1 warning in 7.86s**.

---

## Entry 5 — 2026-10-20 — Document search, date filtering, and upload validation hardening

- **AI tools used:** ChatGPT (GPT-4o); VS Code and PowerShell terminal.
- **Objective:** Add robust document search and filtering (by name, owner, category, date range), and harden file upload validation with chunked streaming and magic number checks.
- **Prompt / request (summary):** Asked the AI to implement search filters on `GET /documents`, validate date ranges, implement incremental UTF-8 text validation to detect split multi-byte characters and null bytes, and verify that search filters never expose documents outside the user's permission scope.
- **AI output / implementation:** Provided filter logic in `app/routers/documents.py`, incremental decoder logic in `app/file_storage.py`, and test cases in `tests/test_documents_api.py` and `tests/test_file_storage.py`.
- **What was specifically wrong with the output or approach:**
  1. The AI applied user-supplied filters (like `owner_id` or `category`) directly to the base `Document` table before or without scoping by the caller's permissions. This allowed a viewer to query `GET /documents?owner_id=1` and see all documents owned by User 1, completely bypassing document grants!
  2. The date filter logic used string matching on ISO timestamps, causing timezone conversion bugs and incorrectly excluding documents created on the boundary date.
  3. In `test_file_storage.py`, the AI wrote async test functions using `pytest.mark.asyncio`, which failed because `pytest-asyncio` was not installed in the environment.
- **Correction / what I did instead:**
  1. Restructured `list_documents()` to enforce the authorization join `or_(Document.owner_id == user.id, DocumentPermission.user_id == user.id)` first as an inescapable security baseline. User filters only narrow down already-accessible documents.
  2. Implemented strict date parsing with UTC timezone boundary arithmetic: `date_from` starts at 00:00:00 UTC and `date_to` uses exclusive upper bound `< date_to + 1 day` 00:00:00 UTC. Added validation rejecting `date_from > date_to` with HTTP 422 (audited).
  3. Rewrote file storage tests as synchronous functions using `asyncio.run()` to eliminate unnecessary external plugin dependencies.
- **Commit link:** [Commit 756884a](https://github.com/Manikanta904/trustvault/commit/756884af8ef042af6140020b8a5f4a462e9c6d07)
- **Verification performed:**
  - Executed `python -m pytest tests/test_file_storage.py -v`: **7 passed in 0.34s** (valid UTF-8, invalid UTF-8 after 32 bytes, null bytes, empty file, invalid PDF header, unsupported extension, and oversized file).
  - Executed `python -m pytest tests/test_documents_api.py -v`: **18 passed in 3.42s** (verifying `test_document_search_does_not_expose_unshared_documents` and `test_document_search_rejects_invalid_date_range`).
  - Full suite run: **52 passed, 2 warnings in 5.80s**.

---

## Entry 6 — 2026-10-21 — Database triggers, transaction atomicity, pagination, safe seeding, and final hardening

- **AI tools used:** Antigravity IDE; PowerShell terminal and Python runtime.
- **Objective:** Close all remaining backend compliance gaps: enforce append-only database triggers on `audit_logs`, decouple foreign-key cascades on document deletion, ensure atomic transaction rollback on audit write failure for delete and download, add document listing pagination, add `document_id` audit filter, audit denied admin and creation attempts, make demo seeding safe and idempotent, exclude database dumps from git, and create complete project documentation.
- **Prompt / request (summary of the actual work):** The user conducted a thorough review against the Snovasys challenge requirements. I was asked to inspect the repository, identify remaining gaps, and implement focused fixes: protect audit logs from tampering via database triggers; preserve historical audit references when documents are deleted; ensure security operations abort if audit writing fails; add pagination to `GET /documents`; audit non-owner document creation and non-admin audit log queries; refactor `seed_demo.py` to remove `Base.metadata.create_all()` and prevent overwriting passwords or reactivating accounts; update `.gitignore` for dumps; and write comprehensive documentation.
- **What was specifically wrong or incomplete (and what was independently checked):**
  1. **Audit log mutability at database layer:** Application endpoints restricted audit records to read-only, but the PostgreSQL database itself lacked triggers to prevent UPDATE, DELETE, or TRUNCATE operations by the application database user.
  2. **FK cascade breaking document deletion with append-only triggers:** Migration `001` configured `audit_logs.document_id` with a foreign key referencing `documents.id`. In PostgreSQL, deleting a document triggered an `ON DELETE SET NULL` cascade on `audit_logs`, which executed an `UPDATE` on the audit log. The append-only trigger intercepted this UPDATE and raised an exception, preventing document owners from deleting their documents!
  3. **Missing atomicity on audit failure:** In document deletion and download endpoints, there were no tests or guarantees that an audit-write failure would abort the sensitive operation. If an audit write failed during deletion, the document might be deleted without an audit trail; if an audit write failed during download, the file might still be transmitted.
  4. **Denial auditing gaps:** Non-owner document creation attempts (`POST /documents`) and non-admin audit log access attempts (`GET /admin/audit-logs`) returned HTTP 403 without logging a `denied` audit entry.
  5. **Seed script risks:** `seed_demo.py` used `Base.metadata.create_all()` (bypassing Alembic) and unconditionally overwrote passwords and reactivated accounts on rerun.
  6. **Listing pagination and dump tracking:** `GET /documents` lacked bounded pagination; `GET /admin/audit-logs` lacked a `document_id` filter; `.gitignore` lacked dump file rules.
- **Correction / what I did instead:**
  1. Created migration `c4e1a8b29f70` adding PostgreSQL PL/pgSQL triggers `audit_logs_no_update_delete` and `audit_logs_no_truncate` on `public.audit_logs`.
  2. Created migration `d7a2c9e4b105` dropping the foreign key constraint `audit_logs_document_id_fkey` on `audit_logs`. This decoupled document deletion from historical audit records: document deletion now succeeds while retaining the original `document_id` integer in immutable audit records.
  3. Atomic transaction handling: Ensured document deletion shares the transaction with the `document_delete` audit record (if audit persistence fails, the deletion rolls back); hardened download so that if audit recording fails, file transmission is aborted with HTTP 500 before file bytes are sent.
  4. Added audit records for access denials: `action="document_create", outcome="denied"` for viewer upload attempts and `action="admin_audit_logs_read", outcome="denied"` for non-admin audit queries.
  5. Refactored `seed_demo.py` to be idempotent: removed `create_all()`, safely skips existing users without modifying passwords or roles, and supports environment variables for non-interactive execution.
  6. Added bounded pagination (`limit` 1-100, `offset` >= 0) to `GET /documents`, added `document_id` filter to `GET /admin/audit-logs`, updated `.gitignore` for `*.dump`, `*.sql`, `*.tar`, and created comprehensive root `README.md`.
- **Commit link:** `[Pending manual commit - uncommitted milestone]` (Local changes ready for user review and commit).
- **Verification performed:**
  - `git diff --check`: **Code 0 (zero whitespace or line-ending errors)**.
  - Final regression test run: `.venv\Scripts\pytest -v` (from `backend`): **80 passed, 3 warnings in 14.10s**.
  - All 80 tests passed across all 7 test suites:
    - `tests/test_admin_api.py`: 17 passed (including `document_id` filtering and non-admin denial auditing)
    - `tests/test_audit_integrity.py`: 3 passed (verifying append-only triggers reject UPDATE, DELETE, TRUNCATE)
    - `tests/test_auth.py`: 8 passed
    - `tests/test_authorization.py`: 7 passed
    - `tests/test_documents_api.py`: 31 passed (including `test_document_delete_is_not_saved_when_audit_fails` and `test_document_download_fails_when_audit_write_fails`)
    - `tests/test_file_storage.py`: 7 passed
    - `tests/test_registration.py`: 7 passed
