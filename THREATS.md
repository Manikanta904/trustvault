# TrustVault — Threat Model

**Last updated:** 2026-10-25
**Status:** Milestone verified with full automated regression suite (**135 passed**, 25 warnings in 35.15s); production deployment controls remain documented as accepted operational risks.

---

## 1. System Overview

TrustVault is a secure document-sharing platform featuring user authentication, role-based capabilities (`admin`, `owner`, `viewer`), granular per-document read/edit permissions, private file storage, and an append-only audit trail.

The backend stack comprises FastAPI, SQLAlchemy 2.0, PostgreSQL with `psycopg`, Alembic, Argon2id password hashing, and PyJWT authentication.

This document records identified threats, concrete attacker scenarios, expected security invariants, implemented code mitigations, mapped automated test verifications, and residual risks. Passing automated test suites prove code-level correctness, but do not replace production infrastructure hardening.

---

## 2. Assets to Protect

- **Uploaded Document Files:** Confidential private files stored in backend storage.
- **Document Metadata & Permissions:** Title, description, category, and access grant records.
- **User Credentials & Tokens:** Argon2 password hashes, JWT secrets, and bearer tokens.
- **Audit Logs:** Forensic evidence of document operations, permission changes, and access denials.
- **Database Relational Integrity:** Schema constraints, append-only triggers, and foreign keys.
- **Application Configuration:** Environment secrets in `.env` and database credentials.

---

## 3. Trust Boundaries

- **Client to API:** All external requests are untrusted until authenticated and authorized.
- **API to Database:** Restricted to application credentials (`trustvault_app`) with minimal necessary privileges.
- **API to File Storage:** Files must only be accessed through server-validated storage paths and authorized routines.
- **User to User:** Cross-user document isolation must be complete unless an explicit grant exists.
- **Administrator to Document Content:** Administrative access to audit logs does not grant access to private document contents.
- **Application to Audit Logs:** The application cannot modify, delete, or truncate audit records due to database-level triggers.
- **Database Administrator Boundary Disclaimer:** Database triggers and role grants protect against application-level compromise, but a PostgreSQL superuser or sufficiently privileged database administrator can alter, bypass, or disable these controls. Absolute tamper-proofing is not claimed.

---

## 4. Threats, Mitigations, and Verification Matrix

### T01: Cross-User Document ID Substitution & Unauthorized Metadata Access
- **Asset & Trust Boundary:** Document metadata; User-to-User boundary.
- **Attacker Capability & Attack Scenario:** An authenticated viewer or unrelated owner inspects network traffic, guesses or enumerates document IDs (e.g. `GET /documents/42`), attempting to view another user's private document metadata.
- **Expected Security Invariant:** An authenticated user can only view document metadata if they are the document owner or hold an active permission grant (`read` or `edit`). Inaccessible documents must return HTTP 404 to prevent enumeration.
- **Mitigation Implemented in Actual Code:** `app/authorization.py` (`get_authorized_document`) checks live database ownership and permissions. If unauthorized, raises HTTP 404. `app/routers/documents.py` (`read_document`) invokes `get_document_or_audit_denial()` which records `action="document_read", outcome="denied"`.
- **Relevant Automated Test Name(s) & Assertions:** `test_ungranted_user_cannot_read_edit_or_delete` (asserts `client.get("/documents/{id}")` returns 404), `test_admin_without_grant_cannot_access_document_api` (asserts admin without grant gets 404), `test_cross_document_access_isolation`.
- **Actual Verification Performed & Result:** Tests executed against PostgreSQL test DB; verified 404 status and denied audit entry created.
- **Residual Risk & Accepted Limitation:** None at application layer. Network eavesdropping mitigated by TLS in production.
- **Status:** **Closed**

### T02: Direct File Download & Authorization Bypass
- **Asset & Trust Boundary:** Confidential document file content; API-to-File-Storage boundary.
- **Attacker Capability & Attack Scenario:** An attacker attempts to call `GET /documents/{id}/download` directly for a document they do not own and have no grant for, hoping file serving bypasses metadata authorization.
- **Expected Security Invariant:** File content delivery requires explicit server-side `read` authorization. No direct filesystem access or unauthenticated static routes exist.
- **Mitigation Implemented in Actual Code:** `app/routers/documents.py` (`download_document`) calls `get_document_or_audit_denial(db, user, document_id, "read")` before resolving the file path. Files are served via `FileResponse` with `attachment` disposition and `X-Content-Type-Options: nosniff`.
- **Relevant Automated Test Name(s) & Assertions:** `test_ungranted_user_cannot_read_edit_or_delete` (asserts download returns 404), `test_admin_without_grant_cannot_access_document_api` (asserts admin download returns 404).
- **Actual Verification Performed & Result:** Verified download requests without grants return HTTP 404 and create denied audit records.
- **Residual Risk & Accepted Limitation:** Once a file is downloaded by an authorized user, server controls cannot prevent that user from sharing their local copy.
- **Status:** **Closed**

### T03: Read-versus-Edit Privilege Escalation
- **Asset & Trust Boundary:** Document metadata modification; User-to-User permission boundary.
- **Attacker Capability & Attack Scenario:** A user granted `read`-only access attempts to send a `PATCH /documents/{id}` request with altered title/metadata, or an ungranted user attempts to update metadata.
- **Expected Security Invariant:** Only document owners and users with explicit `edit` permissions can update document metadata. A `read` grant strictly denies edit operations.
- **Mitigation Implemented in Actual Code:** `app/authorization.py` checks `permission.permission_type == "edit"`. `app/routers/documents.py` (`update_document`) enforces `required_permission="edit"` and rejects empty updates with HTTP 422.
- **Relevant Automated Test Name(s) & Assertions:** `test_read_grant_denies_edit_but_edit_grant_allows_it` (asserts reader `PATCH` returns 404, while editor `PATCH` returns 200), `test_editor_cannot_grant_or_revoke_permissions`.
- **Actual Verification Performed & Result:** Verified read-only grant returns 404 on `PATCH` and records `action="document_edit", outcome="denied"`.
- **Residual Risk & Accepted Limitation:** None.
- **Status:** **Closed**

### T04: Unauthorized Deletion & Permission Management Tampering
- **Asset & Trust Boundary:** Document lifecycle and access control table; Owner privilege boundary.
- **Attacker Capability & Attack Scenario:** A viewer, an editor with `edit` permissions, or another user attempts to delete a document (`DELETE /documents/{id}`) or grant permissions to a third party (`PUT /documents/{id}/permissions/{user_id}`).
- **Expected Security Invariant:** Only the true document creator / owner (`owner_id == user.id`) can delete the document or grant/revoke permissions. While administrators can upload and manage their own documents (commit `59d7883`), administrative status alone does NOT grant permission to manage or delete other users' documents.
- **Mitigation Implemented in Actual Code:** In `app/routers/documents.py`: `delete_document`, `grant_document_permission`, and `revoke_document_permission` strictly check `document.owner_id == user.id`. If false, audits denial and returns HTTP 404. Non-owners (and viewers) cannot create metadata or upload without authorization (`POST /documents/upload` checks `user.role in {"owner", "admin"}`; viewers receive HTTP 403).
- **Relevant Automated Test Name(s) & Assertions:** `test_editor_cannot_grant_or_revoke_permissions` (asserts editor `PUT /permissions` returns 404 and original grant remains unchanged), `test_viewer_cannot_create_document_metadata` (returns 403), `test_viewer_metadata_creation_denial_is_audited`, `tests/test_admin_upload_and_sharing.py` (verifies admin manages own documents but remains isolated from other owners).
- **Actual Verification Performed & Result:** Verified non-owners cannot delete or grant permissions; denied attempts are audited.
- **Residual Risk & Accepted Limitation:** None.
- **Status:** **Closed**

### T05: Access After Permission Revocation & Stale Authorization Cache
- **Asset & Trust Boundary:** Document access post-revocation; Temporal authorization boundary.
- **Attacker Capability & Attack Scenario:** An owner revokes a user's access (`DELETE /documents/{id}/permissions/{user_id}`). The revoked user attempts immediate subsequent requests using their existing JWT, hoping permissions are cached in-memory or in the token.
- **Expected Security Invariant:** Permission revocation takes effect immediately. Every subsequent request must query the current permission state and return HTTP 404.
- **Mitigation Implemented in Actual Code:** Permissions are never embedded in JWTs or memory caches. `app/authorization.py` queries `DocumentPermission` in PostgreSQL on every request. Revocation deletes the row in an atomic transaction.
- **Relevant Automated Test Name(s) & Assertions:** `test_upload_download_grant_and_revoke` (verifies immediate 404 on metadata, download, search, edit, and delete after revocation), `test_revoked_permission_blocks_next_access`.
- **Actual Verification Performed & Result:** Verified that within the same test run, revocation immediately denies all 5 access paths with HTTP 404.
- **Residual Risk & Accepted Limitation:** Revocation controls future server access; it cannot erase files already saved to the recipient's personal computer.
- **Status:** **Closed**

### T06: Search/Listing Leakage & Document Existence Enumeration
- **Asset & Trust Boundary:** Document visibility and discovery; Information disclosure boundary.
- **Attacker Capability & Attack Scenario:** A user queries `GET /documents?owner_id=1` or `GET /documents?search=confidential` attempting to list or infer documents they are not authorized to view.
- **Expected Security Invariant:** Document listing and search must apply ownership and permission scoping before any user-supplied filters. Searching must never disclose the existence of unshared documents. Inaccessible documents must return 404, not 403.
- **Mitigation Implemented in Actual Code:** In `app/routers/documents.py` (`list_documents`), the base query enforces `where(or_(Document.owner_id == user.id, DocumentPermission.user_id == user.id))`. Search terms, owner IDs, categories, and date filters are appended as child conditions. Bounded pagination (`limit`: 1–100, `offset` >= 0) prevents table-dump attacks.
- **Relevant Automated Test Name(s) & Assertions:** `test_document_search_does_not_expose_unshared_documents`, `test_document_listing_shows_shared_documents_only`, `test_document_listing_pagination`.
- **Actual Verification Performed & Result:** Verified unshared documents never appear in list or search results, even when explicitly filtering by the target owner's ID.
- **Residual Risk & Accepted Limitation:** None.
- **Status:** **Closed**

### T07: Malicious, Oversized, Malformed, or Misleading File Uploads
- **Asset & Trust Boundary:** Backend storage and filesystem; Host availability boundary.
- **Attacker Capability & Attack Scenario:** An attacker uploads a 500 MB file to exhaust disk space, an `.exe` disguised as a `.pdf`, malformed UTF-8 text containing null bytes, or an empty 0-byte file.
- **Expected Security Invariant:** Uploads must be strictly bounded in size (10 MB), verified for allowed extensions and MIME types, inspected for binary magic numbers (PDF, PNG, JPEG), validated incrementally for valid UTF-8 without null bytes (TXT), and cleaned up immediately from disk upon failure.
- **Mitigation Implemented in Actual Code:** `app/file_storage.py` (`save_upload`) streams in 64 KB chunks, enforcing `size > 10MB` cutoff, validates headers (`%PDF-`, `\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`), uses incremental UTF-8 decoding, rejects null bytes, and unlinks partial files in `except Exception:`.
- **Relevant Automated Test Name(s) & Assertions:** `test_valid_utf8_text_upload_succeeds`, `test_invalid_utf8_after_first_32_bytes_is_rejected`, `test_null_byte_after_first_32_bytes_is_rejected`, `test_empty_text_upload_is_rejected`, `test_invalid_pdf_signature_is_rejected`, `test_unsupported_extension_is_rejected`, `test_upload_exceeding_size_limit_is_rejected`, `test_upload_commit_failure_cleans_up_file_and_database`.
- **Actual Verification Performed & Result:** All 7 storage test cases passed; verified destination directory is empty after rejected uploads.
- **Residual Risk & Accepted Limitation:** Signature checks verify basic headers, not deep semantic PDF parsing or active malware scanning. Production deployment should add ClamAV or equivalent virus scanning.
- **Status:** **Closed (for application layer controls)**

### T08: File Path Traversal & Storage-Key Manipulation
- **Asset & Trust Boundary:** Host filesystem; Storage abstraction boundary.
- **Attacker Capability & Attack Scenario:** An attacker uploads a file named `../../../../windows/system32/cmd.exe` or manipulates a download request storage key to read files outside private storage.
- **Expected Security Invariant:** Files must be stored exclusively under server-generated random identifiers. Client filenames must never be used as filesystem paths. Storage keys must be strictly validated.
- **Mitigation Implemented in Actual Code:** `app/file_storage.py`: storage keys are generated via `uuid4().hex` (32 hex characters). Filenames are sanitized via `.rsplit("/", 1)[-1]` and stored only as database metadata. `get_storage_path()` strictly validates `len(key) == 32` and `all(c in "0123456789abcdef" for c in key)`.
- **Relevant Automated Test Name(s) & Assertions:** `test_valid_utf8_text_upload_succeeds`, `test_cross_document_access_isolation`.
- **Actual Verification Performed & Result:** Verified stored file names on disk are 32-hex UUIDs and files reside strictly inside `STORAGE_DIR`.
- **Residual Risk & Accepted Limitation:** OS-level directory permissions must be secured during deployment.
- **Status:** **Closed**

### T09: Credential Theft, Inactive Accounts, Token Misuse, & Brute-Force
- **Asset & Trust Boundary:** User accounts and authentication tokens; Authentication boundary.
- **Attacker Capability & Attack Scenario:** An attacker uses stolen password hashes, submits expired or forged JWTs, logs in to deactivated employee accounts, attempts credential stuffing, or registers weak passwords.
- **Expected Security Invariant:** Passwords must be hashed using state-of-the-art Argon2id. Registration must enforce password complexity. Tokens must have validated expiration and signature. Deactivated users must be blocked immediately from login and active token usage. Brute-force attempts must be throttled.
- **Mitigation Implemented in Actual Code:** `app/security.py`: Argon2id password hashing via `pwdlib`. Registration schemas enforce min 8 chars, uppercase, lowercase, digit, and special character regex rules ([`app/schemas.py`](file:///d:/projects/trustvault/backend/app/schemas.py)). JWT signed with `HS256`, verified with required `sub` and `exp`. `get_current_user` queries database to ensure `user.is_active is True`. Failed logins record `outcome="denied"` in audit logs. `login_rate_limiter` in `app/rate_limiter.py` restricts login attempts to 10/min per IP.
- **Relevant Automated Test Name(s) & Assertions:** `test_login_and_get_current_user`, `test_invalid_password_is_rejected`, `test_deactivated_user_cannot_use_existing_token`, `test_expired_jwt_is_rejected`, `tests/test_registration.py` (8 parameterized password complexity rejection tests), `test_phase4_watermark_and_downloads.py::test_17_rate_limiter_blocks_excessive_requests`.
- **Actual Verification Performed & Result:** Verified 401 on bad password, expired token, and deactivated user; verified 422 on weak passwords; verified failed login is recorded in audit log; verified rate limit returns HTTP 429.
- **Residual Risk & Accepted Limitation:** Rate limiting uses in-memory sliding windows (process-local). Multi-worker clusters require distributed Redis.
- **Status:** **Closed (for single-node deployment)**

### T10: Audit Omission, Failure-Path Loss, & Transaction Inconsistency
- **Asset & Trust Boundary:** Audit log completeness and reliability; Transaction boundary.
- **Attacker Capability & Attack Scenario:** An operation succeeds but the audit log fails to write (omission), or an operation fails and rolls back its audit log, concealing the attack attempt.
- **Expected Security Invariant:** Mutating security operations must be atomic with their audit record. If an audit record cannot be written, the business operation must roll back. Upload validation failures must be persisted independently.
- **Mitigation Implemented in Actual Code:** In `app/routers/documents.py`: `update_document`, `grant_document_permission`, `revoke_document_permission`, and `delete_document` write the audit log in the same database transaction before `db.commit()`. If audit write raises an exception, the transaction aborts. `record_upload_failure()` uses a separate session to record rejected uploads.
- **Relevant Automated Test Name(s) & Assertions:** `test_document_update_is_not_saved_when_audit_write_fails`, `test_document_delete_is_not_saved_when_audit_fails`, `test_document_download_fails_when_audit_write_fails`, `test_permission_grant_is_not_saved_when_audit_fails`, `test_permission_revoke_is_not_saved_when_audit_fails`, `test_failed_upload_is_recorded_in_audit_log`.
- **Actual Verification Performed & Result:** All 6 transaction-failure tests pass, proving operations roll back when audit logging fails.
- **Residual Risk & Accepted Limitation:** If PostgreSQL crashes mid-transaction before WAL flush, both operation and audit log roll back consistently.
- **Status:** **Closed**

### T11: Audit Log Tampering, Triggers, & Privileged DBA Compromise
- **Asset & Trust Boundary:** Audit log immutability; Database storage boundary.
- **Attacker Capability & Attack Scenario:** An attacker obtains application SQL injection or compromised application database credentials (`trustvault_app`) and attempts `UPDATE audit_logs SET details = ...` or `TRUNCATE audit_logs` to cover their tracks.
- **Expected Security Invariant:** Audit logs must be append-only. The application role cannot update, delete, or truncate audit rows under any circumstances.
- **Mitigation Implemented in Actual Code:** Migration `c4e1a8b29f70` created PostgreSQL triggers (`audit_logs_no_update_delete` and `audit_logs_no_truncate`) calling `prevent_audit_log_mutation()` which unconditionally raises an exception on `UPDATE`, `DELETE`, or `TRUNCATE`.
- **Relevant Automated Test Name(s) & Assertions:** `tests/test_audit_integrity.py`: `test_audit_log_rejects_update`, `test_audit_log_rejects_delete`, `test_audit_log_rejects_truncate`.
- **Actual Verification Performed & Result:** All 3 integrity tests pass, confirming PostgreSQL raises DBAPIError exceptions on update, delete, or truncate attempts.
- **Residual Risk & Accepted Limitation:** **Crucial Security Boundary Disclosure:** A PostgreSQL superuser or sufficiently privileged database administrator can disable triggers (`ALTER TABLE ... DISABLE TRIGGER`) or drop the table. Application database controls protect against application-level attackers, but cannot defend against a compromised database superuser.
- **Status:** **Partially Mitigated (Application-level tamper-proofing verified; superuser boundary documented)**

### T12: Document Deletion Foreign-Key Cascading vs. Historical Audit Retention
- **Asset & Trust Boundary:** Long-term audit integrity; Relational schema boundary.
- **Attacker Capability & Attack Scenario:** An owner deletes a document (`DELETE /documents/{id}`). If the audit log foreign key has `ON DELETE CASCADE` or `ON DELETE SET NULL`, the historical record of who accessed or uploaded the document is wiped or loses its document ID.
- **Expected Security Invariant:** Deleting a document from active storage must preserve all historical audit logs, including the original numeric `document_id`.
- **Mitigation Implemented in Actual Code:** Migration `d7a2c9e4b105` explicitly dropped the foreign key constraint `audit_logs_document_id_fkey`. `AuditLog.document_id` is an unconstrained integer column. When `Document` is deleted, `audit_logs` rows remain untouched and triggers do not fire.
- **Relevant Automated Test Name(s) & Assertions:** `test_delete_document_keeps_audit_record` in `tests/test_documents_api.py` (deletes document, verifies document row is gone, verifies audit record remains with original `document_id`).
- **Actual Verification Performed & Result:** Verified that after document deletion, the `document_upload` and `document_delete` audit entries retain the original document ID.
- **Residual Risk & Accepted Limitation:** None.
- **Status:** **Closed**

### T13: Secret Leakage, Configuration Exposure, & Repository Hygiene
- **Asset & Trust Boundary:** Secrets, database dumps, and credentials; Source code repository boundary.
- **Attacker Capability & Attack Scenario:** Secrets (`JWT_SECRET`, database passwords) or database dumps containing real user data are committed to git and pushed to a public repository.
- **Expected Security Invariant:** No `.env` files, database dumps (`.dump`, `.sql`), local SQLite databases, or private uploaded files can be committed. Demo seeding scripts must not store hardcoded credentials or overwrite existing user accounts.
- **Mitigation Implemented in Actual Code:** Root `.gitignore` excludes `.env`, `**/.env`, `*.db`, `*.sqlite3`, `*.dump`, `*.sql`, `*.tar`, and `backend/private_storage/`. `seed_demo.py` refactored to be idempotent and safe, removing `create_all()`.
- **Relevant Automated Test Name(s) & Assertions:** `git ls-files` check, `git status` check, `test_seed_demo_accounts_is_safe_and_idempotent` in `tests/test_documents_api.py`.
- **Actual Verification Performed & Result:** Verified `.env` and `trustvault_before_migration.dump` are not tracked; seed script preserves accounts on rerun.
- **Residual Risk & Accepted Limitation:** Developers must exercise discipline never to use `git add -f` on ignored files.
- **Status:** **Closed**

### T14: Leak Attribution, Traceable Watermarking, & Physical/Screenshot Capture Limitations
- **Asset & Trust Boundary:** Proprietary shared document copies; User-to-External/Offline boundary.
- **Attacker Capability & Attack Scenario:** An authorized shared recipient downloads or previews a confidential document and redistributes it externally (via email, upload, or screen capture/photograph), attempting to hide the leak source.
- **Expected Security Invariant:** Every shared preview and download must be dynamically watermarked server-side with the authenticated viewer's identity (email and name), UTC generation timestamp explicitly labeled as UTC, unique document ID, and cryptographic trace reference. Stored original master PDFs must remain unmodified.
- **Mitigation Implemented in Actual Code:** 
  1. `app/watermark.py`: Generates viewer-specific watermarked PDF in-memory using `pypdf` and `reportlab`. Overlays two subtle diagonal banners per page containing viewer name, email, UTC timestamp, and trace ID. Fails closed (HTTP 422) on encrypted or malformed PDFs.
  2. `app/routers/documents.py` (`download_document`): Owner receives original master file; shared viewers receive the generated watermarked copy.
  3. Frontend `DocumentViewer.tsx`: Renders repeated diagonal security watermark overlays during authenticated browser preview.
- **Relevant Automated Test Name(s) & Assertions:** `test_phase4_watermark_and_downloads.py` (`test_01` through `test_08`): Verifies original file checksum is unchanged on disk, viewer-specific watermark contains viewer email and UTC timestamp across all pages, and different users receive distinct watermarks.
- **Actual Verification Performed & Result:** All 8 watermarking automated tests passed; verified watermarked PDF text extraction in automated pytest suite.
- **Crucial Security Limitations & Residual Risks (Explicit Disclosure):**
  1. **Attribution Aid, Not Proof:** A watermark assists forensic attribution by identifying whose authorized account was used to view/download the file. However, it does not constitute legal proof that the named account holder personally leaked or redistributed the document (e.g. account compromise, shoulder-surfing, or unattended workstation).
  2. **Screenshots & External Redistribution:** Technical controls running inside a browser or PDF viewer cannot prevent external physical photography, OS-level screen recording tools, or third-party screen captures.
  3. **No Retroactive Recall:** Once an authorized user downloads a watermarked copy to their local filesystem, subsequent permission revocation terminates future server access but cannot delete or recall already downloaded local files.
- **Status:** **Closed (Application and watermarking controls implemented and verified; offline capture limitations documented)**

### T15: Authentication & Sensitive Operation Rate Limiting (Brute-Force & Enumeration)
- **Asset & Trust Boundary:** Authentication surface and document enumeration; Network-to-Application boundary.
- **Attacker Capability & Attack Scenario:** An attacker launches high-frequency credential stuffing against `/auth/login`, rapid user registration floods against `/auth/register`, or employee directory enumeration against `/users/search`.
- **Expected Security Invariant:** High-frequency abuse must be throttled with HTTP 429 Too Many Requests and a `Retry-After` header before accounts can be compromised or server resources exhausted.
- **Mitigation Implemented in Actual Code:** `app/rate_limiter.py` implements a thread-safe sliding-window rate limiter:
  - `/auth/login`: 10 attempts/minute per IP.
  - `/auth/register`: 5 attempts/minute per IP.
  - `/users/search`: 30 queries/minute per user/IP.
  - `/documents/upload` and bulk sharing: 30 requests/minute per user.
- **Relevant Automated Test Name(s) & Assertions:** `test_phase4_watermark_and_downloads.py::test_17_rate_limiter_blocks_excessive_requests` (asserts HTTP 429 returned after threshold).
- **Actual Verification Performed & Result:** Verified HTTP 429 returned with `Retry-After` header upon exceeding configured limits.
- **Residual Risk & Accepted Limitation:** Current rate limiter is memory-backed (single instance). Multi-instance horizontal scaling requires a shared backend (such as Redis) to synchronize sliding windows across processes.
- **Status:** **Closed (for single-node deployment)**

### T16: Document Filter & Search Metadata Privacy
- **Asset & Trust Boundary:** Document repository metadata; User isolation boundary.
- **Attacker Capability & Attack Scenario:** A user filters documents by owner name or email (`GET /documents?owner_search=...`) or category, hoping the filter bypasses document authorization and reveals metadata or titles of unauthorized documents.
- **Expected Security Invariant:** Filters must only operate on the subset of documents that the caller is already authorized to access (either as owner or through an active permission grant). Unauthorized documents must never be returned.
- **Mitigation Implemented in Actual Code:** In `app/routers/documents.py` (`list_documents`), base access predicate `or_(Document.owner_id == user.id, DocumentPermission.user_id == user.id)` is applied first. The `owner_search` query parameter performs an inner join on `User` and filters only within the authorized set. Document response schemas safely include `owner_name`, `owner_email`, and `user_permission` without exposing sensitive user hashes or unrelated account metadata.
- **Relevant Automated Test Name(s) & Assertions:** `test_phase4_watermark_and_downloads.py::test_18_owner_search_filter_returns_only_authorized_documents`.
- **Actual Verification Performed & Result:** Verified unshared documents matching owner email are not returned to unrelated callers.
- **Residual Risk & Accepted Limitation:** None.
- **Status:** **Closed**

### T17: Shared Viewer Download Audit Visibility for Document Owners
- **Asset & Trust Boundary:** Document owner audit visibility; Document owner visibility boundary.
- **Attacker Capability & Attack Scenario:** A shared user downloads a document, but the document owner has no visibility into who accessed or downloaded their document, preventing accountability.
- **Expected Security Invariant:** Shared downloads must be logged with actor identity and made visible to the document owner through a dedicated, owner-scoped activity view without exposing other users' private documents.
- **Mitigation Implemented in Actual Code:** `app/routers/documents.py`: `GET /documents/{document_id}/activity` checks `document.owner_id == user.id`, queries `AuditLog` joined with `User`, and returns download and preview history with actor display name, email, and timestamp. Denied for non-owners (HTTP 404).
- **Relevant Automated Test Name(s) & Assertions:** `test_phase4_watermark_and_downloads.py::test_14_owner_activity_and_admin_audit_visibility`.
- **Actual Verification Performed & Result:** Verified owner receives download events with recipient name/email; unrelated user gets 404.
- **Residual Risk & Accepted Limitation:** Relies on in-app activity view. Email notification is not configured by default.
- **Status:** **Closed**

---

## 5. Security Invariants Summary

1. **Mandatory Authentication:** All protected endpoints reject unauthenticated requests with HTTP 401.
2. **Explicit Authorization:** Ownership or an explicit per-document grant is mandatory for reading, downloading, or editing.
3. **Privilege Separation:** `read` permission allows viewing and watermarked downloading; `edit` allows metadata modification; neither allows deletion or permission management.
4. **Watermarked Shared Delivery:** Shared downloads always stream a viewer-specific watermarked PDF with UTC timestamp and trace reference; only the owner downloads the original stored file.
5. **Owner-Only Lifecycle:** Only the document owner can delete the document or grant/revoke permissions.
6. **Immediate Revocation:** Revoking permission blocks subsequent requests immediately on the live database.
7. **Admin Isolation:** Administrators cannot read or download document contents without an explicit document grant.
8. **Storage Isolation:** Private files are stored under random 32-hex keys outside the web root and never served through static directories.
9. **Append-Only Auditing:** Audit rows cannot be updated, deleted, or truncated by the application role due to database triggers and privilege grants.
10. **Enumeration Resistance:** Unauthorized and missing document requests uniformly return HTTP 404.

---

## 6. Accepted and Outstanding Risks (Explicitly Marked Unimplemented Items)

- **Malware Scanning (Not Implemented):** The backend validates file signatures, UTF-8 validity, and file size limits. Comprehensive virus/malware scanning (e.g. ClamAV daemon) is NOT implemented at the application layer and must be deployed at the container/infrastructure layer.
- **Encryption at Rest (Not Implemented):** Uploaded files and database tables are stored in cleartext on the filesystem; transparent disk encryption (e.g., LUKS, BitLocker, or AWS KMS) is NOT implemented at the application layer and must be provided by the hosting environment.
- **Database Hash-Chaining (Not Implemented):** Evaluated during threat modeling; rejected in favor of PostgreSQL append-only triggers and restricted role privileges (`REVOKE UPDATE, DELETE ON audit_logs`). Hash chaining without external hardware roots (HSM) adds concurrency overhead without preventing a database superuser from rewriting the chain.
- **Token Revocation Blacklist (Not Implemented):** JWT tokens cannot be revoked before their expiration. However, document permission revocation is enforced live in PostgreSQL on every request, completely neutralizing token longevity for document access.
- **Database Superuser Privilege:** Database triggers prevent mutation by `trustvault_app`, but cannot stop a PostgreSQL superuser. WORM (Write-Once-Read-Many) storage is recommended for enterprise compliance.
- **Screenshots & Offline Leakage:** Technical controls cannot stop physical photography, display scraping, or external distribution of already downloaded files. Watermarking provides attribution aid, not leak prevention.
- **Distributed Rate Limiting:** Rate limiting uses in-memory sliding windows. A distributed Redis cluster is recommended for multi-instance deployments.

---

## 7. Verification Record

- **2026-10-19:** Registration test suite passed (7 passed). Full test suite passed (24 passed).
- **2026-10-20:** Admin audit endpoint verified through Swagger and automated tests. File storage tests passed (7 passed). Document API tests passed (11 passed). Full suite passed (44 passed).
- **2026-10-21:** Hardening milestone: verified document listing pagination, admin audit log filtering by document ID, denial audit logging for non-owners and non-admins, transaction abort on delete/download audit failure, safe demo seeding without schema mutation, append-only trigger protections, and git repository hygiene (80 passed).
- **2026-10-24:** Phase 4 Security Hardening & Traceable Watermarking:
  - Server-side PDF watermarking with viewer identity, UTC timestamp, document ID, and trace reference (`app/watermark.py`).
  - Owner original vs. shared watermarked download policy (`app/routers/documents.py`).
  - Owner document activity & download history endpoint (`/documents/{id}/activity`).
  - Owner name/email search filters and repository identity visibility.
  - Rate limiting on authentication, user search, and sensitive document operations.
  - Complete backend test suite: **122 passed, 0 failed in 30.44s** (`.venv\Scripts\pytest -q`).
  - Frontend production build: **Passed with 0 errors** (`npm run build`).
  - Frontend lint: **Passed with 0 errors and 0 warnings** (`npm run lint`).
- **2026-10-25:** Registration Hardening, Admin PDF Sharing, and Final Documentation:
  - Added password complexity validators (min 8 chars, uppercase, lowercase, digit, special character) in backend schema and frontend registration form.
  - Interactive password visibility toggles restored on registration page.
  - Permitted administrator PDF document upload and discretionary sharing (`user.role in {"owner", "admin"}`).
  - Full backend test suite: **135 passed, 25 warnings in 35.15s** (`.venv\Scripts\pytest.exe -v`).
  - Frontend production build: **Passed with 0 errors** (`npm run build`).
  - Frontend lint: **Passed with 0 errors and 0 warnings** (`npm run lint`).

