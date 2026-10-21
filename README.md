# TrustVault

TrustVault is a secure, role-based document sharing and auditing platform developed for the Snovasys Fresher Hiring Challenge 2026. The backend is built with FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, JWT authentication, Argon2id password hashing, and private file storage.

---

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

From the `backend` directory:

```bash
# Run interactive seed script
python seed_demo.py
```

For unattended / scriptable provisioning, set environment variables prior to running:

```bash
export DEMO_PASSWORD_ADMIN="YourSecurePass123!"
export DEMO_PASSWORD_OWNER="YourSecurePass123!"
export DEMO_PASSWORD_VIEWER="YourSecurePass123!"
python seed_demo.py
```

Default demo accounts provisioned:
- **Admin:** `admin@example.com` (`admin` role)
- **Owner:** `owner@example.com` (`owner` role)
- **Viewer:** `viewer@example.com` (`viewer` role)

*Note: Rerunning `seed_demo.py` will detect existing accounts and safely skip them without modifying passwords or roles.*

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
```

---

## 9. Role and Permission Matrix

| Operation | Unauthenticated | Viewer (No Grant) | Viewer (`read`) | Viewer (`edit`) | Document Owner | Administrator |
|---|---|---|---|---|---|---|
| Register Account (`POST /auth/register`) | Allowed (creates `owner`) | Allowed | Allowed | Allowed | Allowed | Allowed |
| Login (`POST /auth/login`) | Allowed | Allowed | Allowed | Allowed | Allowed | Allowed |
| Current User Info (`GET /auth/me`) | 401 | Allowed | Allowed | Allowed | Allowed | Allowed |
| Upload Document (`POST /documents/upload`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed | 403 (Denied) |
| Create Metadata (`POST /documents`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed | 403 (Denied) |
| List Documents (`GET /documents`) | 401 | Visible grants only | Visible grants only | Visible grants only | Own + shared | Own + shared only |
| Read Metadata (`GET /documents/{id}`) | 401 | 404 (Denied) | Allowed | Allowed | Allowed | 404 (Denied) |
| Download File (`GET /documents/{id}/download`) | 401 | 404 (Denied) | Allowed | Allowed | Allowed | 404 (Denied) |
| Update Metadata (`PATCH /documents/{id}`) | 401 | 404 (Denied) | 404 (Denied) | Allowed | Allowed | 404 (Denied) |
| Delete Document (`DELETE /documents/{id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| Grant Permission (`PUT /documents/{id}/permissions/{user_id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| Revoke Permission (`DELETE /documents/{id}/permissions/{user_id}`) | 401 | 404 (Denied) | 404 (Denied) | 404 (Denied) | Allowed | 404 (Denied) |
| View Audit Logs (`GET /admin/audit-logs`) | 401 | 403 (Denied) | 403 (Denied) | 403 (Denied) | 403 (Denied) | Allowed |

*Notice:* Inaccessible documents return `404 Not Found` rather than `403 Forbidden` to prevent document-existence enumeration by unauthorized callers.

---

## 10. Audit Logging and Security Controls

TrustVault records audit events for:
- User login attempts (success and denied invalid credentials / deactivated accounts)
- Document uploads, upload validation failures, and non-owner upload rejections
- Document metadata read, list, and search queries
- Document downloads, missing file conditions, and unauthorized download attempts
- Document updates, empty updates, and unauthorized update attempts
- Document deletions, unauthorized deletion attempts, and preserved audit references
- Permission grants, self-grant rejections, invalid target user rejections, and unauthorized grant attempts
- Permission revocations, missing grant rejections, and unauthorized revocation attempts
- Non-admin attempts to access the administrative audit API

All security-sensitive operations persist their business changes and required audit log in the same atomic database transaction. If the audit event cannot be saved, the transaction is rolled back and the business operation is aborted.

---

## 11. Known Limitations and Deliberately Omitted Features

1. **No In-Memory Permission Caching:** Caching permission checks in Redis or JWTs was deliberately omitted. While caching reduces database reads, it introduces a window where revoked users can continue accessing documents until cache expiry. TrustVault prioritizes immediate, real-time revocation over micro-optimization.
2. **Reverse-Proxy Rate Limiting:** Login rate limiting, IP throttling, and DDoS protection are not implemented inside FastAPI application code; in accordance with cloud-native security patterns, these should be handled at the ingress/reverse proxy layer (e.g. Nginx, Cloudflare).
3. **Antivirus / Malware Scanning:** Basic file magic number validation, extension allowlisting, and incremental UTF-8 inspection are enforced. Full semantic scanning (e.g. ClamAV daemon) is deferred to production infrastructure.
4. **Superuser Boundary:** Database triggers protect audit records against application-level compromise, but cannot prevent alterations by a PostgreSQL superuser. Absolute tamper-proofing is honestly disclaimed.

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
pytest -v
```

---

## 13. Snovasys Hiring Challenge Deliverables Status

- [x] **Backend Architecture & Code:** Fully implemented with FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, JWT, and Argon2id.
- [x] **Ten Required Functionalities:** Fully implemented and verified.
- [x] **Three Mandatory Security Standards:** Server-side authorization, trustworthy audit logging, and immediate revocation verified with 80 automated tests.
- [x] **Audit Protections:** PostgreSQL append-only triggers and migration-managed constraints verified.
- [x] **Evidence-Based Documentation:** `README.md`, `PROMPTS.md` (with real commit links and AI mistake documentation), and `THREATS.md` (full threat matrix) updated.
- [ ] **Frontend Application:** Ready to begin; backend API is frozen and prepared for UI integration.
- [ ] **Public Git Repository:** Repository will remain **private** until the submission deadline, as strictly mandated by Snovasys instructions.
- [ ] **Live Deployed URL:** Pending deployment following frontend completion.
- [ ] **Five-Minute Demo Video & Write-Up:** Scheduled for preparation after frontend completion.
