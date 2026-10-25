# TrustVault Frontend

Modern, enterprise-grade React/TypeScript frontend for **TrustVault** — Secure Document Sharing with an Immutable Audit Trail (Snovasys Fresher Hiring Challenge 2026).

- **Live Production Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)
- **Live Production Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)

---

## Architecture & Technology Stack

- **Framework:** React 19 + TypeScript + Vite 8
- **Routing:** React Router DOM v7
- **Styling:** Tailwind CSS v4 (`@tailwindcss/vite`) with curated dark-navy & clean slate palette
- **Branding & Assets:** Purple shield security favicon (`public/favicon.svg`) with white lock core matching TrustVault enterprise brand
- **Icons:** Lucide React
- **HTTP Client:** Axios with centralized request/response interceptors and error handling
- **State & Context:** Typed `AuthProvider` with token storage in `localStorage` and automatic 401 handling

---

## Directory Structure

```text
frontend/
├── public/
│   └── favicon.svg              # Bespoke purple shield security favicon
├── src/
│   ├── api/                     # Centralized typed API layer
│   │   ├── client.ts            # Axios instance, interceptors, error extraction
│   │   ├── auth.ts              # Login, Register, GetMe, Health endpoints
│   │   ├── documents.ts         # Upload, List/Search, Update, Delete, Download
│   │   ├── permissions.ts       # Grant and Revoke endpoints
│   │   ├── users.ts             # Employee directory search
│   │   └── admin.ts             # Admin audit log API
│   ├── components/
│   │   ├── common/
│   │   │   └── ProtectedRoute.tsx # Auth & role-based route guard
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx    # Responsive shell
│   │   │   ├── Header.tsx       # Breadcrumb, status, profile badge
│   │   │   └── Sidebar.tsx      # Dark navy sidebar with role-aware nav
│   │   └── documents/
│   │       ├── UploadModal.tsx  # Drag & drop upload (.pdf, .txt, <=10MB)
│   │       ├── EditDocumentModal.tsx # Update metadata (title, category, desc)
│   │       ├── ShareModal.tsx   # Per-document grant/revoke with immediate effect
│   │       ├── DocumentViewer.tsx # In-browser authenticated PDF viewer with watermark
│   │       └── DeleteConfirmModal.tsx # Delete confirmation with audit notice
│   ├── context/
│   │   ├── auth-context.ts      # Context definition
│   │   ├── AuthContext.tsx      # AuthProvider component
│   │   └── useAuth.ts           # useAuth custom hook
│   ├── pages/
│   │   ├── LoginPage.tsx        # Login with quick-fill demo buttons
│   │   ├── RegisterPage.tsx     # Registration with password visibility toggles
│   │   ├── DashboardPage.tsx    # Overview metrics, recent documents
│   │   ├── DocumentsPage.tsx    # Document repository with search & filters
│   │   ├── DocumentDetailsPage.tsx # Detailed metadata & security details
│   │   ├── SharedDocumentsPage.tsx # Documents shared by other owners
│   │   ├── AdminAuditPage.tsx   # Immutable audit trail viewer with filters
│   │   ├── ProfilePage.tsx      # User profile & security scope
│   │   └── NotFoundPage.tsx     # 404 page
│   ├── types/
│   │   └── index.ts             # TypeScript definitions matching backend
│   ├── App.tsx                  # Main router configuration
│   ├── main.tsx                 # React DOM mount point
│   └── index.css                # Tailwind imports & base styles
├── .env.example                 # Environment configuration template
├── package.json
└── vite.config.ts               # Vite config with backend proxy
```

---

## Getting Started

### 1. Prerequisites
- Node.js 18+ (tested with Node 20+)
- Running TrustVault backend on `http://127.0.0.1:8000`

### 2. Installation
```bash
cd D:\projects\trustvault\frontend
npm install
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
In local development, leave `VITE_API_BASE_URL=` blank. The Vite dev server proxy in `vite.config.ts` automatically forwards `/auth`, `/documents`, `/admin`, `/users`, and `/health` requests to `http://127.0.0.1:8000`, completely avoiding browser CORS preflight blocking.

For production builds targeting the hosted backend, set:
```env
VITE_API_BASE_URL=https://trustvault-back.onrender.com
```

### 4. Running the Development Server
```bash
npm run dev
```
The frontend will start at `http://localhost:5173`.

### 5. Production Build & Linting
```bash
npm run lint    # ESLint verification (0 errors, 0 warnings)
npm run build   # TypeScript typecheck and production bundle build
```

### 6. Browser Favicon Hard-Refresh
If your browser caches the old favicon after updating:
- **Windows / Linux:** Press `Ctrl + F5` or `Ctrl + Shift + R` while on the site tab.
- **macOS:** Press `Cmd + Shift + R`.
- Alternatively, clear browser cache for the site or open in an Incognito / Private window.

---

## Demonstration Accounts & Local Setup

> [!WARNING]
> **LOCAL-DEMO-ONLY CREDENTIALS**: The credentials below are strictly for local evaluation and hackathon testing. Never deploy or reuse these credentials in staging, production, or publicly reachable environments.

For local evaluation, TrustVault provisions three standard demonstration accounts:

| Role | Email | Password | Purpose / Access Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@example.com` | `123456789abc` | Immutable audit log inspection & admin PDF sharing. |
| **Document Owner** | `owner@example.com` | `123456789abc` | Document upload, metadata management, deletion, and access sharing. |
| **Document Viewer** | `viewer@example.com` | `123456789abc` | Read and watermarked download access to shared documents. |

### Quick-Fill Demo Controls & Security Protection

On the login page (`LoginPage.tsx`), quick-fill buttons are provided for **Admin**, **Owner**, and **Viewer**.
- In local development (`npm run dev`) or when `VITE_DEMO_PASSWORD` is configured in `.env`, clicking any demo button automatically pre-fills both the verified email and the local demo password (`123456789abc`).
- **Production Credential Exposure Prevention**: In production builds where demo environment flags are absent, pre-filled demo passwords and demonstration controls are automatically omitted to prevent shipping hardcoded credentials in client bundles.

### Seeding Demo Accounts in the Backend

Demo accounts are provisioned via `seed_demo.py` in the `backend/` directory:

```bash
cd D:\projects\trustvault\backend

# Standard safe provisioning (creates demo accounts with default password: 123456789abc)
python seed_demo.py

# Explicit credential synchronization (ensures existing accounts match standard local password)
python seed_demo.py --sync-credentials
```

*Note on Credentials:* Passwords in TrustVault are hashed with Argon2id (`pwdlib`) and are never stored in plaintext.

---

## Security Verification & Workflow Features

1. **Server-Side Authorization Truth:**
   - Every read, download, edit, or delete action is validated by the FastAPI backend against live database records.
2. **Immediate Revocation Demonstration:**
   - When an owner revokes access to a user via `ShareModal`, subsequent download attempts by the revoked user immediately return HTTP 404.
3. **Private File Storage:**
   - Files are stored on disk using random 32-hex UUIDv4 storage keys. Physical storage keys are never exposed over the API or rendered in client HTML.
4. **Interactive Password Visibility Controls:**
   - `RegisterPage.tsx` provides accessible, secure eye toggles to inspect password and password confirmation inputs before submission.
5. **Administrator PDF Upload & Sharing:**
   - Administrators can upload compliance documents and grant discretionary access to employees while remaining isolated from other users' documents.
6. **Tamper-Resistant Audit Viewer:**
   - Restricted to `admin` accounts. Displays immutable logs created and protected by PostgreSQL PL/pgSQL append-only triggers.
7. **No Client Role Escalation:**
   - Registration strictly assigns the role of `owner` on the server; public users cannot self-assign administrative privileges.
