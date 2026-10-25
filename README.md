# TrustVault

TrustVault is a secure, role-based document sharing and auditing platform developed for the Snovasys Fresher Hiring Challenge 2026. The backend is built with FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, JWT authentication, Argon2id password hashing, private file storage, and dynamic traceable PDF watermarking.

- **Live Production Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)
- **Live Production Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)
- **Interactive Swagger UI:** [https://trustvault-back.onrender.com/docs](https://trustvault-back.onrender.com/docs)
- **Health Verification:** [https://trustvault-back.onrender.com/health](https://trustvault-back.onrender.com/health)

---

## Technical Documentation Index (`docs/`)

TrustVault includes comprehensive, evidence-based technical documentation in `docs/`:

| Document | Primary Focus & Coverage |
|---|---|
| [**`ARCHITECTURE.md`**](file:///d:/projects/trustvault/docs/ARCHITECTURE.md) | High-level system architecture, technology stack, Mermaid data flow diagrams, and subsystem breakdown |
| [**`API-SECURITY.md`**](file:///d:/projects/trustvault/docs/API-SECURITY.md) | Authentication cryptography, JWT claims, IDOR/enumeration defenses, file validation, and audit triggers |
| [**`API.md`**](file:///d:/projects/trustvault/docs/API.md) | Exhaustive REST API specification for all 19 active endpoints with request/response schemas |
| [**`DATABASE.md`**](file:///d:/projects/trustvault/docs/DATABASE.md) | PostgreSQL schema definitions, Mermaid ER diagram, Alembic migrations, and append-only triggers |
| [**`DEPLOYMENT.md`**](file:///d:/projects/trustvault/docs/DEPLOYMENT.md) | Clean-clone local setup guide, environment variables, Render hosting details, and CORS analysis |
| [**`SECURITY-TESTING.md`**](file:///d:/projects/trustvault/docs/SECURITY-TESTING.md) | Automated test suite layout, test isolation fixtures, and breakdown of all 135 passed tests |
| [**`PERMISSIONS.md`**](file:///d:/projects/trustvault/docs/PERMISSIONS.md) | Discretionary access control (DAC), role behaviors, Mermaid permission evaluation flow, and denial matrix |
| [**`LIMITATIONS.md`**](file:///d:/projects/trustvault/docs/LIMITATIONS.md) | Explicit disclosure of security boundaries, hardware limitations, watermarking limits, and unverified areas |
| [**`DEMO.md`**](file:///d:/projects/trustvault/docs/DEMO.md) | 5-minute technical demonstration script with timestamp breakdown and safe account provisioning |
| [**`WRITEUP.md`**](file:///d:/projects/trustvault/docs/WRITEUP.md) | Formal hiring challenge submission write-up, engineering trade-offs, and genuine AI correction log |

## 1. Architecture and Security Principles

TrustVault is built on defense-in-depth principles:
- **Server-Side Authorization on Every Request:** Every document read, update, download, delete, and permission change is authorized on the server. Client-side controls are never assumed to be security boundaries.
- **Three Core Roles:**
  - `admin`: Manages platform oversight, monitors audit logs, and inspects system activity. Administrative role alone does not grant access to private document contents.
  - `owner`: Creates documents, manages metadata, uploads/downloads files, grants and revokes access, and deletes documents.
  - `viewer`: Reads metadata and downloads documents only when granted explicit permission by the document owner; can update metadata if granted `edit` permission.
- **Per-Document Granular Permissions:** Document owners grant `read` or `edit` permissions to named active users.
- **Immediate Revocation:** Revoking permission takes effect immediately in the database. Any subsequent attempt to access the document returns `404 Not Found`.
- **Append-Only Audit Evidence:** Security-sensitive events (logins, uploads, downloads, updates, deletions, permission changes, and denied requests) are recorded in an append-only audit trail protected by database-level triggers.
- **Private File Storage:** Uploaded files are stored under server-generated random keys (UUIDv4) in a private directory that is never exposed as a public static mount. Path traversal is prevented through strict key validation.
- **Credential Protection:** Passwords are hashed using Argon2 (`pwdlib[argon2]`). JWTs use HMAC-SHA256 (`HS256`) with secret keys loaded strictly from environment configuration.

---

## 2. Prerequisites

- **Python:** 3.11 or higher (Python 3.13 recommended)
- **Database:** PostgreSQL 15 or higher
- **Package Manager:** `pip` / virtual environment (`venv`)
- **Shell / OS:** Windows PowerShell, Linux bash, or macOS zsh

---

## 3. Environment Configuration

Copy or create `.env` in `backend/.env`. A template is provided below. Never commit real credentials or secrets to version control.

```env
# Primary application database URL (PostgreSQL with psycopg driver)
DATABASE_URL=postgresql+psycopg://<app_user>:<app_password>@localhost:5432/trustvault

# Dedicated test database URL (must target trustvault_test for pytest isolation)
DATABASE_URL_TEST=postgresql+psycopg://<app_user>:<app_password>@localhost:5432/trustvault_test

# JWT secret key (must be at least 32 characters of high-entropy randomness)
JWT_SECRET=your-random-32-character-or-longer-secret-key-here

# JWT expiration window in minutes (default: 30)
JWT_EXPIRE_MINUTES=30

# Optional private storage path override (defaults to backend/private_storage)
# TRUSTVAULT_STORAGE_DIR=/absolute/path/to/private_storage
```

---

## 4. PostgreSQL Database Setup

Connect to PostgreSQL as a database administrator (e.g., `postgres`) and create the databases and restricted application role:

```sql
-- Create databases
CREATE DATABASE trustvault;
CREATE DATABASE trustvault_test;

-- Create restricted application user
CREATE USER trustvault_app WITH PASSWORD 'your_secure_password';

-- Grant connection privileges
GRANT CONNECT ON DATABASE trustvault TO trustvault_app;
GRANT CONNECT ON DATABASE trustvault_test TO trustvault_app;

-- Grant schema privileges in the target database
\c trustvault
GRANT USAGE, CREATE ON SCHEMA public TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO trustvault_app;

-- Repeat privileges in test database
\c trustvault_test
GRANT USAGE, CREATE ON SCHEMA public TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO trustvault_app;
```

---

## 5. Alembic Database Migrations

Database schemas must always be applied through Alembic migrations. Never use `Base.metadata.create_all()` in production or seed scripts.

From the `backend` directory:

```bash
# Upgrade the database schema to the latest revision
alembic upgrade head

# Inspect the current migration revision
alembic current

# View migration history
alembic history --verbose
```

### Migration History
1. `fa9d3cc8788d`: Creates `users` table with Argon2 password hashes, role constraints (`admin`, `owner`, `viewer`), and active flags.
2. `96d86a251001`: Creates `documents`, `document_permissions`, and `audit_logs` tables with constraints and indexes.
3. `c4e1a8b29f70`: Adds database-level trigger `prevent_audit_log_mutation()` to block `UPDATE`, `DELETE`, and `TRUNCATE` operations on `audit_logs`.
4. `d7a2c9e4b105`: Preserves historical `document_id` in audit records after document deletion by decoupling the foreign-key cascade.

---

## 6. Safe Demo Seed Script

The demo seeding script (`seed_demo.py`) safely provisions initial demo accounts without overwriting existing accounts, changing existing roles, or reactivating disabled accounts.

> [!WARNING]
> **LOCAL-DEMO-ONLY CREDENTIALS**: The credentials below are strictly for local evaluation and hackathon testing. Never deploy or reuse these credentials in any staging, production, or publicly reachable environment.

### Standard Local Demo Accounts
- **Admin:** `admin@example.com` / `123456789abc` (`admin` role — audit logs & compliance)
- **Owner:** `owner@example.com` / `123456789abc` (`owner` role — document creation, editing, & sharing)
- **Viewer:** `viewer@example.com` / `123456789abc` (`viewer` role — granted document access)

Passwords are never stored in plaintext; all accounts are hashed using Argon2id (`pwdlib`).

From the `backend` directory:

```bash
# 1. Provision demo accounts (safe & idempotent; skips accounts that already exist)
python seed_demo.py

# 2. Explicitly synchronize existing demo accounts to standard local credentials
python seed_demo.py --sync-credentials
```

For custom unattended / scriptable provisioning, set environment variables prior to running:

```bash
export DEMO_PASSWORD_ADMIN="YourCustomPass123!"
export DEMO_PASSWORD_OWNER="YourCustomPass123!"
export DEMO_PASSWORD_VIEWER="YourCustomPass123!"
python seed_demo.py
```

*Note: Rerunning `seed_demo.py` without flags detects existing accounts and safely skips them without altering passwords, roles, or active statuses. To intentionally reset demo account passwords back to the standard local credentials, run with `--sync-credentials`.*


---

## 7. Running the API Server

From the `backend` directory:

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux / macOS

# Start FastAPI application
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### API Documentation URLs
- **Swagger UI (Interactive):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc (Alternative Reference):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema (JSON):** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- **Health Check:** `GET http://127.0.0.1:8000/health`

---

## 8. Running Automated Tests

Tests execute against the isolated `trustvault_test` database. `tests/conftest.py` automatically applies migrations before testing and ensures tests never execute against the primary development database.

From the `backend` directory:

```bash
# Run the complete test suite
pytest -v

# Run targeted test suites
pytest tests/test_auth.py
pytest tests/test_authorization.py
pytest tests/test_documents_api.py
pytest tests/test_admin_api.py
pytest tests/test_file_storage.py
pytest tests/test_audit_integrity.py
pytest tests/test_registration.py
pytest tests/test_phase4_watermark_and_downloads.py
pytest tests/test_admin_upload_and_sharing.py

# Run complete regression suite (135 tests)
pytest -q
```

---

## 9. Role and Permission Matrix

| Operation | Unauthenticated | Viewer (No Grant) | Viewer (`read`) | Viewer (`edit`) | Document Owner | Administrator |
|---|---|---|---|---|---|---|
| Register Account (`POST /auth/register`) | Allowed (creates `owner`) | Allowed | Allowed | Allowed | Allowed | Allowed |
| Login (`POST /auth/login`) | Allowed | Allowed | Allowed | Allowed | Allowed | Allowed |
| Current User Info (`GET /auth/me`) | 401 | Allowed | Allowed | Allowed | Allowed | Allowed |
| Upload Document (`POST /documents/upload`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed | Allowed (PDF) |
| Create Metadata (`POST /documents`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed | Allowed |
| List Documents (`GET /documents`) | 401 | Visible grants only | Visible grants only | Visible grants only | Own + shared | Own + shared only |
| Read Metadata (`GET /documents/{id}`) | 401 | 404 (Denied) | Allowed | Allowed | Allowed | 404 (Denied) |
| In-Browser Preview (`GET /documents/{id}/view`) | 401 | 404 (Denied) | Allowed (Watermarked) | Allowed (Watermarked) | Allowed | 404 (Denied) |
| Download Original (`GET /documents/{id}/download`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed (Original) | 404 (Denied) |
| Download Shared (`GET /documents/{id}/download`) | 401 | 404 (Denied) | Allowed (Watermarked) | Allowed (Watermarked) | Allowed (Original) | 404 (Denied) |
| Update Metadata (`PATCH /documents/{id}`) | 401 | 404 (Denied) | 404 (Denied) | Allowed | Allowed | 404 (Denied) |
| Delete Document (`DELETE /documents/{id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| Grant Permission (`PUT /documents/{id}/permissions/{user_id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| Revoke Permission (`DELETE /documents/{id}/permissions/{user_id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| Owner Activity History (`GET /documents/{id}/activity`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| View Audit Logs (`GET /admin/audit-logs`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed |

*Notice:* Inaccessible documents return `404 Not Found` rather than `403 Forbidden` to prevent document-existence enumeration by unauthorized callers.

### Sensitive Endpoint API Specification

| Endpoint | Method | Required Role | Document Permission | Request Format | Success Response | Expected Failure Behavior |
|---|---|---|---|---|---|---|
| `/auth/login` | POST | Public | None | `application/x-www-form-urlencoded` (`username`, `password`) | 200 OK (`access_token`, `token_type`, `user`) | 400 (Bad input), 401 (Invalid credentials/inactive), 429 (Rate limit: >10/min) |
| `/auth/register` | POST | Public | None | JSON (`name`, `email`, `password`) | 201 Created (`id`, `name`, `email`, `role`, `created_at`) | 400 (Duplicate email), 422 (Password <8 chars, missing upper/lower/digit/special), 429 (Rate limit: >5/min) |
| `/auth/me` | GET | Any authenticated | None | Header: `Authorization: Bearer <token>` | 200 OK (`id`, `name`, `email`, `role`, `is_active`) | 401 (Missing/expired/invalid token) |
| `/users/search` | GET | `owner`, `admin` | None | Query: `q` (name or email prefix) | 200 OK (`list[UserSearchItem]`) | 401 (Unauthorized), 403 (Viewer role), 429 (Rate limit: >30/min) |
| `/documents/upload` | POST | `owner`, `admin` | Owner (creator) | Multipart form: `file`, `title`, `description`, `category` | 201 Created (`DocumentResponse`) | 401 (Unauth), 403 (Viewer role), 413 (>10MB), 415 (Invalid signature/MIME), 429 (>30/min) |
| `/documents` | GET | Any authenticated | Caller's scope | Query: `search`, `category`, `owner_search`, `date_from`, `date_to`, `limit`, `offset` | 200 OK (`list[DocumentResponse]`) | 401 (Unauthorized), 422 (Invalid date bounds) |
| `/documents/{id}` | GET | Any authenticated | Owner OR `read` OR `edit` | Header: `Authorization: Bearer <token>` | 200 OK (`DocumentResponse`) | 401 (Unauthorized), 404 (Unshared/nonexistent) |
| `/documents/{id}/view` | GET | Any authenticated | Owner OR `read` OR `edit` | Header: `Authorization: Bearer <token>` | 200 OK (Streaming PDF, headers: `inline`, `no-store`) | 401 (Unauthorized), 404 (Unshared/nonexistent) |
| `/documents/{id}/download` | GET | Any authenticated | Owner (Original) OR `read`/`edit` (Watermarked) | Header: `Authorization: Bearer <token>` | 200 OK (Owner: original file; Shared: watermarked PDF) | 401 (Unauthorized), 404 (Unshared/revoked), 422 (Non-PDF shared download fail-closed) |
| `/documents/{id}` | PATCH | Any authenticated | Owner OR `edit` | JSON: `title`, `description`, `category` | 200 OK (`DocumentResponse`) | 401 (Unauthorized), 404 (Unshared/read-only caller), 422 (Empty payload) |
| `/documents/{id}` | DELETE | `owner` | Document Owner only | Header: `Authorization: Bearer <token>` | 204 No Content | 401 (Unauthorized), 404 (Non-owner/unshared) |
| `/documents/{id}/permissions/{user_id}` | PUT | `owner` | Document Owner only | JSON: `permission_type` (`read` or `edit`) | 200 OK (`PermissionResponse`) | 401 (Unauthorized), 404 (Non-owner, self-grant, target not found) |
| `/documents/{id}/permissions/{user_id}` | DELETE | `owner` | Document Owner only | Header: `Authorization: Bearer <token>` | 204 No Content | 401 (Unauthorized), 404 (Non-owner, ungranted user) |
| `/documents/{id}/permissions/bulk` | POST | `owner` | Document Owner only | JSON: `permission_type` (`read` or `edit`) | 200 OK (`BulkPermissionResponse`) | 401 (Unauthorized), 404 (Non-owner), 429 (Rate limit: >30/min) |
| `/documents/{id}/permissions/bulk` | DELETE | `owner` | Document Owner only | Header: `Authorization: Bearer <token>` | 200 OK (`BulkRevokeResponse`) | 401 (Unauthorized), 404 (Non-owner), 429 (Rate limit: >30/min) |
| `/documents/{id}/activity` | GET | `owner` | Document Owner only | Header: `Authorization: Bearer <token>` | 200 OK (`DocumentActivityResponse`) | 401 (Unauthorized), 404 (Non-owner) |
| `/admin/audit-logs` | GET | `admin` | Platform Admin only | Query: `limit`, `offset`, `document_id` | 200 OK (`list[AuditLogResponse]`) | 401 (Unauthorized), 403 (Non-admin caller) |

---

## 10. Audit Logging and Security Controls

TrustVault records audit events for:
- User login attempts (success and denied invalid credentials / deactivated accounts)
- Document uploads, upload validation failures, and non-owner upload rejections
- Document metadata read, list, and search queries
- Document in-browser previews (`document_view`) and unauthorized preview attempts
- Document original downloads by owner and watermarked downloads by shared recipients (`document_download`)
- Document updates, empty updates, and unauthorized update attempts
- Document deletions, unauthorized deletion attempts, and preserved audit references
- Permission grants, bulk sharing, and unauthorized grant attempts
- Permission revocations, bulk revocation, and unauthorized revocation attempts
- Non-admin attempts to access the administrative audit API

### Traceable Watermarking Policy
- **Owner Downloads:** Downloads the original bit-for-bit master PDF stored in private storage.
- **Shared Viewer Downloads:** Generates a separate, viewer-specific watermarked PDF in-memory using `pypdf` and `reportlab`. Applies two subtle diagonal banners per page containing viewer name, email, explicit UTC timestamp, document ID, trace reference, and confidentiality notice. Stored master files remain completely unmodified. Fails closed (HTTP 422) on corrupt or encrypted files.
- **In-Browser Preview:** Protected authenticated stream with repeated diagonal watermark overlays.

---

## 11. Known Limitations and Deliberately Omitted Features

1. **Attribution Aid, Not Proof:** Watermarking identifies whose account downloaded a file, assisting leak investigation. It does not provide legal proof that the named person personally leaked it (e.g. account theft or shoulder surfing).
2. **Screenshots & Offline Leakage:** Technical controls cannot prevent external camera photography or OS-level screen capture. Already downloaded files cannot be remotely deleted from client storage.
3. **No In-Memory Permission Caching:** Caching permission checks in Redis or JWTs was deliberately omitted. While caching reduces database reads, it introduces a window where revoked users can continue accessing documents until cache expiry. TrustVault prioritizes immediate, real-time revocation over micro-optimization.
4. **Antivirus / Malware Scanning (Not Implemented):** Basic file magic number validation, extension allowlisting, and incremental UTF-8 inspection are enforced. Full semantic scanning (e.g. ClamAV daemon) is deferred to production infrastructure.
5. **Database Superuser Privilege:** Database triggers protect audit records against application-level compromise, but cannot prevent alterations by a PostgreSQL superuser. Absolute tamper-proofing is honestly disclaimed.

---

## 12. Clean-Clone Setup Walkthrough

To verify reproducibility from a clean environment:

```bash
# 1. Clone repository
git clone https://github.com/Manikanta904/trustvault.git
cd trustvault/backend

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows (.venv/bin/activate on Unix)

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (.env)
cp .env.example .env  # or create .env as shown in Section 3

# 5. Apply migrations
alembic upgrade head

# 6. Seed demo accounts safely
python seed_demo.py

# 7. Execute automated regression suite
pytest -q

# 8. Run Frontend
cd ../frontend
npm install
npm run build
npm run dev
```

---

## 13. Snovasys Hiring Challenge Deliverables Status

- [x] **Backend Architecture & Code:** Fully implemented with FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, JWT, Argon2id, and ReportLab/PyPDF watermarking.
- [x] **Ten Required Functionalities:** Fully implemented and verified.
- [x] **Three Mandatory Security Standards:** Server-side authorization, trustworthy audit logging, and immediate revocation verified with 135 automated tests.
- [x] **Traceable Watermarking & Shared Downloads:** Fully implemented and verified across preview and download endpoints.
- [x] **Audit Protections:** PostgreSQL append-only triggers and migration-managed constraints verified.
- [x] **Evidence-Based Documentation:** 10 dedicated documents in `docs/`, along with `README.md`, `PROMPTS.md` (with real commit links and AI correction logs), and `THREATS.md` (full threat matrix).
- [x] **Frontend Application:** Fully implemented with React 19, TypeScript, Vite, Tailwind CSS, Lucide icons, responsive layout, purple shield security favicon, and bulk sharing controls.
- [x] **Live Deployed URLs:** Verified accessible on Render:
  - Frontend: [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)
  - Backend: [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)
- [x] **Five-Minute Demo Video & Write-Up:** Detailed script and submission write-up provided in [`docs/DEMO.md`](file:///d:/projects/trustvault/docs/DEMO.md) and [`docs/WRITEUP.md`](file:///d:/projects/trustvault/docs/WRITEUP.md).
- [ ] **Public Git Repository:** Repository remains **private** until the submission deadline, as strictly mandated by Snovasys instructions.
