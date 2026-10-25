# TrustVault — API Security & Threat Mitigation

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Live Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)  
**Live Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)

---

## 1. Authentication & Token Security Architecture

TrustVault implements stateless JWT bearer authentication coupled with live database user state verification on every protected request.

### 1.1 Password Protection & Hashing
- **Algorithm:** Argon2id via `pwdlib` (`PasswordHash.recommended()`) in [`app/security.py:29`](file:///d:/projects/trustvault/backend/app/security.py#L29).
- **Salt & Key Derivation:** Argon2id handles salt generation and memory-hard key derivation automatically, preventing GPU/ASIC rainbow-table attacks.
- **Complexity Enforcement:** Validated on registration in [`app/schemas.py:24-36`](file:///d:/projects/trustvault/backend/app/schemas.py#L24-L36):
  - Minimum 8 characters (maximum 128).
  - Minimum 1 uppercase letter (`[A-Z]`).
  - Minimum 1 lowercase letter (`[a-z]`).
  - Minimum 1 decimal digit (`[0-9]`).
  - Minimum 1 special character (`[^A-Za-z0-9\s]`).

### 1.2 JWT Encoding and Verification
- **Signature Algorithm:** Pinned to `HS256` (HMAC-SHA256). Asymmetric algorithm confusion attacks are completely neutralized because `algorithms=["HS256"]` is explicitly pinned during decoding.
- **Secret Key Entropy:** Minimum 32 characters enforced at server initialization:
  ```python
  if len(JWT_SECRET) < 32:
      raise RuntimeError("Set a unique JWT_SECRET of at least 32 characters in backend/.env")
  ```
- **Token Claims:** Includes `sub` (User ID string), `role` (user role), `iat` (issued-at UTC timestamp), and `exp` (expiration UTC timestamp).
- **Expiration Window:** Default 30 minutes (`JWT_EXPIRE_MINUTES=30`).
- **Claim Assertions:** Token decoding in [`app/security.py:80-85`](file:///d:/projects/trustvault/backend/app/security.py#L80-L85) strictly requires the presence of both `sub` and `exp` claims (`options={"require": ["sub", "exp"]}`). Tokens missing either claim are immediately rejected with HTTP 401.

### 1.3 Active Account State Enforcement
- The JWT access token is stateless, but the dependency `get_current_user()` ([`app/security.py:69-95`](file:///d:/projects/trustvault/backend/app/security.py#L69-L95)) queries the database on every authenticated request:
  ```python
  user = db.get(User, user_id)
  if user is None or not user.is_active:
      raise unauthorized
  ```
- If an employee account is deactivated (`is_active = False`), all existing tokens issued to that user become immediately useless for further API calls.

---

## 2. Authorization & Discretionary Access Control (DAC)

### 2.1 Live Database Lookup vs. Stale Token Caching
A common flaw in modern web applications is caching user permissions inside the JWT payload. If permissions are cached in the token, a user whose access was revoked retains unauthorized access until their token expires (up to 30 minutes).

TrustVault completely rejects token-cached permissions. The authorization helper `get_authorized_document()` ([`app/authorization.py:9-75`](file:///d:/projects/trustvault/backend/app/authorization.py#L9-L75)) checks the live PostgreSQL `document_permissions` table on every single request. When an owner revokes access, the permission row is deleted in an atomic transaction; the next request from the revoked recipient immediately fails.

### 2.2 Insecure Direct Object Reference (IDOR) & Enumeration Defenses
- **URL Tampering:** An attacker attempting to access `GET /documents/105` without an active grant cannot view metadata, preview content, or download files.
- **Uniform HTTP 404 Response:** When an unauthorized user requests a document they do not own and have no grant for, the server responds with:
  ```json
  {"detail": "Document not found"}
  ```
  Responding with HTTP 403 Forbidden would confirm to an attacker that document #105 exists. By returning uniform HTTP 404 for both nonexistent documents and unauthorized documents, TrustVault eliminates document existence enumeration.

---

## 3. Storage & Ingestion Security

### 3.1 Strict Storage Key Isolation
- Uploaded files are saved in `backend/private_storage/` under server-generated 32-hex random identifiers (`uuid4().hex`).
- Client-supplied filenames (`original_filename`) are sanitized of directory traversal sequences (`../`, `\`, null bytes) and stored strictly as database metadata.
- Storage paths are resolved via `get_storage_path(storage_key)` ([`app/file_storage.py:140-155`](file:///d:/projects/trustvault/backend/app/file_storage.py#L140-L155)), which enforces:
  - Exact 32-character length.
  - Strict hexadecimal alphabet check (`0-9a-f`).
  - Path resolution strictly within `STORAGE_DIR`.

### 3.2 Ingestion Validation Pipeline
1. **Size Enforcement:** File uploads are streamed in 64 KB chunks. If total bytes exceed 10 MB (`10 * 1024 * 1024`), the upload aborts immediately with HTTP 413 Payload Too Large.
2. **MIME & Extension Pairing:** Validated against `ALLOWED_TYPES` allowlist (`.pdf`, `.txt`, `.png`, `.jpg`, `.jpeg`).
3. **Magic Byte Signature Inspection:**
   - PDF: must begin with `%PDF-`.
   - PNG: must begin with `\x89PNG\r\n\x1a\n`.
   - JPEG: must begin with `\xff\xd8\xff`.
4. **Incremental UTF-8 Decoding:** For `.txt` files, `codecs.getincrementaldecoder("utf-8")` decodes chunks continuously across 64 KB boundaries to detect split multi-byte UTF-8 sequences. Any null byte (`\x00`) or decoding error immediately raises HTTP 415.
5. **Atomic Cleanup:** If ingestion or database insertion fails, partial files on disk are immediately unlinked via `destination.unlink(missing_ok=True)`.

---

## 4. Traceable Dynamic PDF Watermarking

Shared document downloads stream a dynamically watermarked PDF generated in-memory:
- **Master PDF Protection:** Original files in `backend/private_storage/` are never modified.
- **Attribution Metadata Overlay:**
  - Authenticated viewer's full name and email address.
  - Generation timestamp explicitly marked with UTC timezone (`YYYY-MM-DD HH:MM:SS UTC`).
  - Numeric Document ID and unique cryptographic trace reference (`TRC-{id}-{uuid[:8]}`).
  - Confidentiality notice and total page counter (`Page X/Y`).
- **Placement & Styling:** Two diagonal banners per page rotated at 32 degrees with low opacity (~0.18) so document text remains readable while watermarks resist simple cropping.
- **Fail-Closed Principle:** If a PDF is encrypted or corrupt, watermarking aborts with HTTP 422 Unprocessable Entity; unwatermarked master files are never leaked to shared recipients.

---

## 5. Defensive HTTP Response Headers

Streaming and download endpoints emit hardened security headers ([`app/routers/documents.py:1092-1098`](file:///d:/projects/trustvault/backend/app/routers/documents.py#L1092-L1098)):

| Header | Value | Security Objective |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-confusion attacks and browser MIME-type sniffing. |
| `Cache-Control` | `private, no-store, must-revalidate` | Prevents intermediate proxies and shared caches from storing private documents. |
| `X-Frame-Options` | `SAMEORIGIN` | Defends against clickjacking by preventing external iframe embedding. |
| `Content-Security-Policy` | `frame-ancestors 'self'` | Modern standard restricting frame embedding strictly to the trusted origin. |

---

## 6. Sliding-Window Rate Limiting

Thread-safe sliding-window rate limiters in [`app/rate_limiter.py`](file:///d:/projects/trustvault/backend/app/rate_limiter.py) guard sensitive application surfaces against brute-force and enumeration:

| Protected Surface | Configured Limit | Identification Key | Action on Exceeded Limit |
|---|---|---|---|
| **User Login** (`/auth/login`) | 10 req / 60 sec | Client IP address | HTTP 429 + `Retry-After` header; audit event recorded |
| **Registration** (`/auth/register`) | 5 req / 60 sec | Client IP address | HTTP 429 + `Retry-After` header; audit event recorded |
| **User Search** (`/users/search`) | 30 req / 60 sec | `user_{id}` / IP | HTTP 429 + `Retry-After` header; audit event recorded |
| **Uploads & Bulk Grants** | 30 req / 60 sec | `user_{id}` | HTTP 429 + `Retry-After` header; audit event recorded |

---

## 7. Forensic Audit Logging & Immutability

### 7.1 Database-Level Immutability (Migration `c4e1a8b29f70`)
Application-layer write restrictions can be bypassed if an attacker compromises application database credentials. TrustVault moves audit protection into the database engine via PostgreSQL triggers:
```sql
CREATE OR REPLACE FUNCTION public.prevent_audit_log_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs are append-only';
END;
$$;

CREATE TRIGGER audit_logs_no_update_delete
BEFORE UPDATE OR DELETE ON public.audit_logs
FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_log_mutation();

CREATE TRIGGER audit_logs_no_truncate
BEFORE TRUNCATE ON public.audit_logs
FOR EACH STATEMENT EXECUTE FUNCTION public.prevent_audit_log_mutation();
```

### 7.2 Independent Failure Persistence
When an upload fails validation, FastAPI rolls back the main request transaction (`db.rollback()`). To ensure rejected attacks are not erased, `record_upload_failure()` ([`app/routers/documents.py:48-62`](file:///d:/projects/trustvault/backend/app/routers/documents.py#L48-L62)) opens an independent database session (`SessionLocal()`) to commit failure audit entries independently of the primary transaction.

---

## 8. Summary: Implemented Controls vs. Known Residual Risks

| Threat Category | Implemented Defensive Control | Residual Risk / Accepted Limitation |
|---|---|---|
| **Brute-Force Login** | 10 req/min sliding-window rate limiter + Argon2id | In-memory limiter is process-local; multi-node clusters require distributed Redis. |
| **Privilege Escalation** | Registration hardcoded to `role="owner"`; admin endpoints require `user.role == "admin"` | None at application layer. |
| **Unauthorized Document Access** | Server-side live DB checks on every request; uniform 404 on denial | None at application layer. |
| **Path Traversal** | Filenames stripped of path characters; random 32-hex UUIDv4 storage keys | File storage depends on OS filesystem permissions. |
| **Audit Tampering** | PostgreSQL PL/pgSQL triggers reject `UPDATE`, `DELETE`, `TRUNCATE` | A PostgreSQL superuser (`postgres`) can bypass or disable triggers. |
| **Data Leakage via Shared Copy** | Dynamic PDF watermarking stamps viewer name, email, UTC timestamp, trace ref | Watermarks do not prevent camera photography or screen recording. |
| **Malware Ingestion** | Magic bytes, extension allowlist, and incremental UTF-8 checking | Deep semantic antivirus scanning (e.g. ClamAV) is not implemented in Python. |
