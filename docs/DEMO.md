# TrustVault — Five-Minute Technical Demonstration Script

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Live Frontend:** [https://trustvault-ui-obkw.onrender.com](https://trustvault-ui-obkw.onrender.com)  
**Live Backend:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)  
**Demo Duration:** 5 Minutes (300 Seconds)

---

## 1. Local Demonstration Setup & Account Reset

> [!WARNING]
> **LOCAL-DEMO-ONLY CREDENTIALS**: The credentials below are strictly for local evaluation and hackathon testing. Never deploy or reuse these credentials in any staging, production, or publicly reachable environment.

### Local Demonstration Accounts
For local evaluation, TrustVault provisions three demonstration accounts via `seed_demo.py`:

| Role | Email Address | Default Local Demo Password | Intended Evaluation Workflow |
|---|---|---|---|
| **Administrator** | `admin@example.com` | `123456789abc` | Audit log inspection, compliance review, and admin PDF sharing |
| **Document Owner** | `owner@example.com` | `123456789abc` | Document upload, metadata management, and discretionary access sharing |
| **Document Viewer** | `viewer@example.com` | `123456789abc` | Accessing shared documents and evaluating watermarked delivery |

### Provisioning / Reset Command
From the `backend/` directory:

```bash
# 1. Provision demo accounts (skips accounts that already exist):
python seed_demo.py

# 2. Reset existing demo accounts back to standard local evaluation credentials:
python seed_demo.py --sync-credentials
```

*Note on Production:* In production deployments on Render, demo accounts are not automatically provisioned unless the seed script was run against the production database. Evaluators can create fresh accounts via `/register` or verify existing accounts.

---

## 2. Minute-by-Minute Demonstration Walkthrough

### Part 1: Architecture, Registration & Role Authentication (0:00 – 0:45)
- **Action:** Open browser to the live frontend (`https://trustvault-ui-obkw.onrender.com/login`).
- **Showcase:**
  - Note the brand identity: clean purple shield with white security padlock.
  - Click **Register** (`/register`). Demonstrate password complexity validation (min 8 chars, uppercase, lowercase, digit, special character).
  - Demonstrate interactive password visibility toggle (eye icon) revealing/masking password input.
  - Return to `/login`. In local development, demo quick-fill buttons automatically populate credentials; in production, enter credentials manually.
  - Log in as **Document Owner** (`owner@example.com`).
- **Key Talking Point:** "Registration strictly hardcodes `role='owner'` on the server; public users cannot self-elevate to administrative privileges."

### Part 2: Document Upload, Magic-Byte Ingestion & Private Storage (0:45 – 1:30)
- **Action:** Navigate to **Documents** repository (`/documents`).
- **Showcase:**
  - Click **Upload Document**.
  - Drag and drop a confidential PDF file (e.g. `Q3_Financial_Audit.pdf`), enter category `Finance`, and submit.
  - Show upload progress and successful ingestion toast.
- **Key Talking Point:** "Files are ingested via chunked 64 KB streams, validated for magic byte signatures (`%PDF-`), capped at 10 MB, and stored under a random 32-hex UUIDv4 key in a private directory outside the web root."

### Part 3: Discretionary Access Control & Granular Sharing (1:30 – 2:30)
- **Action:** From the uploaded document card/row, click **Share Document** (users icon).
- **Showcase:**
  - The `ShareModal` appears. Use the employee search bar (`/users/search`) to search for `viewer`.
  - Notice the search excludes the calling owner and deactivated accounts.
  - Select **TrustVault Viewer** (`viewer@example.com`), choose permission level **Read Only**, and click **Grant Access**.
  - Show the bulk sharing summary toggle: "Share with All Active Employees" provisions grants in a single atomic transaction.
- **Key Talking Point:** "TrustVault employs discretionary access control: only the document creator controls access grants. Permissions are written directly to PostgreSQL and take effect immediately."

### Part 4: Dynamic Watermarked Delivery vs. Owner Master Download (2:30 – 3:30)
- **Action:**
  - While logged in as **Owner**, click **Download**. Show that the owner receives the unwatermarked original master PDF.
  - Open an incognito/private browser window, navigate to the frontend, and log in as **Document Viewer** (`viewer@example.com`).
  - Navigate to **Shared with Me** (`/shared`). Notice the document appears with the `Shared by: TrustVault Owner` badge.
  - Click **View Document** (`/documents/{id}/view`). Show authenticated in-browser preview with anti-framing headers.
  - Click **Download Document** (`/documents/{id}/download`).
  - Open the downloaded PDF: showcase the two subtle diagonal watermark banners on every page containing:
    1. Viewer's full name and email: `TrustVault Viewer (viewer@example.com)`
    2. Explicit UTC timestamp: `2026-10-25 12:xx:xx UTC`
    3. Document ID & cryptographic trace reference: `TRC-xx-xxxxxxxx`
    4. Confidentiality notice: `CONFIDENTIAL • FOR AUTHORIZED USE ONLY`
- **Key Talking Point:** "The master file on disk remains completely untouched. Watermarks are stamped dynamically in-memory before transmission, embedding forensic traceability while failing closed on corrupt files."

### Part 5: Immediate Revocation & IDOR / Enumeration Defense (3:30 – 4:15)
- **Action:**
  - Switch back to the **Owner** window. Open the Share modal for the document, click **Revoke** on `viewer@example.com`, and confirm.
  - Switch back to the **Viewer** window immediately without logging out.
  - Refresh the page or click Download again on the revoked document.
  - Show that the request immediately fails with **HTTP 404 Not Found** ("Document not found").
  - Attempt direct URL tampering: type `/documents/999` or tamper with the document ID in the browser URL bar. Show that both inaccessible and nonexistent documents return uniform HTTP 404.
- **Key Talking Point:** "Permissions are never cached in JWTs or memory caches. Revoking a database row terminates access instantaneously on the next request. Uniform HTTP 404 prevents document existence enumeration."

### Part 6: Append-Only Audit Trail & Administrator Inspection (4:15 – 5:00)
- **Action:**
  - Log out and log in as **Administrator** (`admin@example.com`).
  - Attempt to view the owner's private document metadata: show that even administrators receive HTTP 404 without an explicit grant!
  - Click **Audit Trail** in the sidebar (`/admin/audit`).
  - Showcase the complete chronological audit log table:
    - Login events (`login: success`)
    - Document upload events (`document_upload: success`)
    - Permission grant events (`permission_grant: success`)
    - Download events (`document_download: success` with viewer attribution)
    - Permission revoke events (`permission_revoke: success`)
    - Denied access attempts (`document_download: denied`, `document_read: denied`)
  - Demonstrate filters: filter by Action (`document_download`), Outcome (`denied`), or Document ID.
- **Key Talking Point:** "Every sensitive operation and security denial is permanently recorded in PostgreSQL. Database triggers prevent any application update, deletion, or truncation of audit logs."

---

## 3. Demonstration Summary Checklist

- [x] Password complexity and interactive visibility toggles verified on registration.
- [x] Document upload with magic byte inspection and private storage verified.
- [x] Granular per-document sharing (`read` vs `edit`) demonstrated.
- [x] Dynamic in-memory PDF watermarking with viewer identity and UTC timestamp verified.
- [x] Immediate permission revocation demonstrated on live database.
- [x] Cross-user document isolation and uniform HTTP 404 enumeration defense demonstrated.
- [x] Zero-trust administrator boundary demonstrated (admin cannot access unshared documents).
- [x] Append-only audit trail and administrative inspection demonstrated.
