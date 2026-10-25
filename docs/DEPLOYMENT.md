# TrustVault — Deployment & Environment Configuration Guide

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Verified Production Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)  
**Verified Production Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)

---

## 1. Verified Live Deployment Infrastructure

| Component | Hosting Provider | Live URL | Deployment Type | Health Check Status |
|---|---|---|---|---|
| **Frontend** | Render | `https://trustvault-ui-obkw.onrender.com` | Static Web Site | **Verified Reachable** |
| **Backend** | Render | `https://trustvault-back.onrender.com` | Web Service (Python) | **Verified Reachable (`{"status":"ok"}`)** |
| **Database** | Render | Internal PostgreSQL Service | Managed PostgreSQL 15+ | **Active in production** |

---

## 2. Local Setup from Clean Clone

### 2.1 Prerequisites
- **Python:** 3.11+ (Python 3.13 recommended)
- **Node.js:** 18+ (tested with Node 20+)
- **Database:** PostgreSQL 15+ running on `localhost:5432`
- **Shell:** Windows PowerShell, Linux Bash, or macOS Zsh

### 2.2 PostgreSQL Local Database Preparation
Connect to PostgreSQL using `psql` or pgAdmin as the administrative user (e.g. `postgres`):

```sql
-- 1. Create primary development and dedicated test databases
CREATE DATABASE trustvault;
CREATE DATABASE trustvault_test;

-- 2. Create restricted application user
CREATE USER trustvault_app WITH PASSWORD 'your_secure_password';

-- 3. Grant connection privileges
GRANT CONNECT ON DATABASE trustvault TO trustvault_app;
GRANT CONNECT ON DATABASE trustvault_test TO trustvault_app;

-- 4. Grant schema creation and table privileges
\c trustvault
GRANT USAGE, CREATE ON SCHEMA public TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO trustvault_app;

\c trustvault_test
GRANT USAGE, CREATE ON SCHEMA public TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trustvault_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO trustvault_app;
```

### 2.3 Backend Installation & Startup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate Python virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\activate
# Linux / macOS Bash:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create backend/.env configuration
cp .env.example .env
# Edit backend/.env to provide your DATABASE_URL, DATABASE_URL_TEST, and a random 32+ character JWT_SECRET

# 5. Apply Alembic migrations to create tables and PL/pgSQL triggers
alembic upgrade head

# 6. Seed local demonstration accounts (safe and idempotent)
python seed_demo.py

# 7. Execute automated test suite (verifies 135 tests against trustvault_test)
pytest -q

# 8. Start local API server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2.4 Frontend Installation & Startup

```bash
# 1. Navigate to frontend directory
cd ../frontend

# 2. Install dependencies
npm install

# 3. Create frontend/.env configuration
cp .env.example .env

# 4. Verify TypeScript compilation and ESLint rules
npm run lint
npm run build

# 5. Start development server with Vite reverse proxy
npm run dev
# Application accessible at: http://localhost:5173
```

---

## 3. Environment Variable Specifications

### 3.1 Backend Variables (`backend/.env`)

| Variable Name | Required | Example / Description |
|---|---|---|
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://trustvault_app:password@localhost:5432/trustvault` |
| `DATABASE_URL_TEST` | **Yes** | `postgresql+psycopg://trustvault_app:password@localhost:5432/trustvault_test` |
| `JWT_SECRET` | **Yes** | High-entropy random string (at least 32 characters; raises error if shorter) |
| `JWT_EXPIRE_MINUTES` | No | Token lifetime in minutes (default: `30`) |
| `TRUSTVAULT_STORAGE_DIR`| No | Absolute path to file storage (defaults to `backend/private_storage`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (e.g. `https://trustvault-ui-obkw.onrender.com`) |
| `DEMO_DEFAULT_PASSWORD` | No | Fallback demo password for `seed_demo.py` (default: `123456789abc`) |

### 3.2 Frontend Variables (`frontend/.env`)

| Variable Name | Purpose in Local Development | Purpose in Production Deployment |
|---|---|---|
| `VITE_API_BASE_URL` | Leave blank (`VITE_API_BASE_URL=`). The Vite dev proxy forwards requests to `http://127.0.0.1:8000`. | Set to live backend URL: `https://trustvault-back.onrender.com` |
| `VITE_DEMO_PASSWORD` | Local pre-fill password for demo buttons (`123456789abc`). | Omitted or overridden in production to prevent hardcoding credentials in bundles. |

---

## 4. Production Deployment on Render

### 4.1 Backend Service Configuration on Render
- **Environment:** Python 3.11+
- **Build Command:** `pip install -r requirements.txt && alembic upgrade head`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment Settings:**
  - `DATABASE_URL`: Connection string to Render PostgreSQL instance.
  - `JWT_SECRET`: High-entropy 32+ character random secret.
  - `JWT_EXPIRE_MINUTES`: `30`
  - `CORS_ORIGINS`: `https://trustvault-ui-obkw.onrender.com` *(Crucial: allows the production frontend)*

### 4.2 Frontend Static Site Configuration on Render
- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `dist`
- **Environment Settings:**
  - `VITE_API_BASE_URL`: `https://trustvault-back.onrender.com`

---

## 5. Critical Deployment Verifications & Recommended Improvements

### 5.1 Production CORS Origin Alignment
- **Discovered Situation:** In [`backend/app/main.py:48-52`](file:///d:/projects/trustvault/backend/app/main.py#L48-L52), `default_origins` hardcodes an earlier URL (`https://trustvault-secure-ahte.onrender.com`).
- **Production Solution:** The backend code dynamically reads `CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")` and appends all comma-separated values to the allowed list ([`main.py:54-59`](file:///d:/projects/trustvault/backend/app/main.py#L54-L59)).
- **Action Required on Render Dashboard:** Ensure the backend service has `CORS_ORIGINS=https://trustvault-ui-obkw.onrender.com` configured.
- **Recommended Future Code Fix:** In the next code release, update `default_origins` in `main.py` and `test_auth.py` to directly include `https://trustvault-ui-obkw.onrender.com`.

### 5.2 Ephemeral File Storage vs. Persistent Render Disks
- **Architecture Note:** Render Web Services use ephemeral container storage. Uploaded files placed in `backend/private_storage/` will be wiped whenever the backend container restarts, sleeps, or redeploys unless a persistent disk is attached.
- **Verification Status:** Whether the production Render service has a mounted Render Disk attached to `TRUSTVAULT_STORAGE_DIR` is **UNVERIFIED** without access to Render infrastructure settings.
- **Production Recommendation:** Attach a Render Persistent Disk mounted at `/var/data/trustvault` and configure `TRUSTVAULT_STORAGE_DIR=/var/data/trustvault` in the backend environment.

### 5.3 Database Migration & Trigger Execution
- **Architecture Note:** The build command on Render must include `alembic upgrade head` to ensure migrations `c4e1a8b29f70` (PL/pgSQL triggers) and `d7a2c9e4b105` (foreign key decoupling) are applied to the production database.
- **Verification Status:** Live backend health check (`/health`) returns HTTP 200 `{"status":"ok"}`. Specific trigger existence on the remote production database is **UNVERIFIED** without direct PostgreSQL administrative access to Render.
