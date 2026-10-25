# TrustVault — REST API Reference Documentation

**Project:** TrustVault — Secure Role-Based Document Sharing & Audit Platform  
**Target:** Snovasys Fresher Hiring Challenge 2026  
**Live Backend Service:** [https://trustvault-back.onrender.com](https://trustvault-back.onrender.com)  
**Local Base URL:** `http://127.0.0.1:8000`

---

## 1. Interactive Documentation & Schema Endpoints

TrustVault provides standard OpenAPI 3.1 specifications and interactive Swagger documentation:

| Endpoint | Method | Authentication | Description | Live URL |
|---|---|---|---|---|
| `/docs` | `GET` | Public | Interactive Swagger UI documentation with Try-It-Out | [Swagger UI](https://trustvault-back.onrender.com/docs) |
| `/redoc` | `GET` | Public | ReDoc structured alternative API reference | [ReDoc](https://trustvault-back.onrender.com/redoc) |
| `/openapi.json` | `GET` | Public | Raw OpenAPI 3.1 JSON schema document | [OpenAPI JSON](https://trustvault-back.onrender.com/openapi.json) |
| `/health` | `GET` | Public | Application health verification (`{"status":"ok"}`) | [Health Check](https://trustvault-back.onrender.com/health) |

---

## 2. API Route Summary Matrix (19 Active Endpoints)

| Group | Method | Path | Required Role | Required Document Grant |
|---|---|---|---|---|
| **Auth** | `POST` | `/auth/register` | Public | None |
| **Auth** | `POST` | `/auth/login` | Public | None |
| **Auth** | `GET` | `/auth/me` | Any Authenticated | None |
| **Health** | `GET` | `/health` | Public | None |
| **Users** | `GET` | `/users/search` | `owner`, `admin` | None (Active users only) |
| **Documents** | `POST` | `/documents/upload` | `owner`, `admin` | Creator becomes Document Owner |
| **Documents** | `POST` | `/documents` | `owner`, `admin` | Metadata-only creation (legacy/testing) |
| **Documents** | `GET` | `/documents` | Any Authenticated | Caller's accessible scope (Own + Shared) |
| **Documents** | `GET` | `/documents/{id}` | Any Authenticated | Owner OR `read` OR `edit` |
| **Documents** | `PATCH`| `/documents/{id}` | Any Authenticated | Owner OR `edit` |
| **Documents** | `DELETE`| `/documents/{id}` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Documents** | `GET` | `/documents/{id}/view` | Any Authenticated | Owner OR `read` OR `edit` |
| **Documents** | `GET` | `/documents/{id}/download`| Any Authenticated | Owner (Original) OR `read`/`edit` (Watermarked) |
| **Documents** | `GET` | `/documents/{id}/activity`| `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `GET` | `/documents/{id}/permissions` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `GET` | `/documents/{id}/permissions/bulk-summary` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `POST`| `/documents/{id}/permissions/bulk` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `DELETE`| `/documents/{id}/permissions/bulk` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `PUT` | `/documents/{id}/permissions/{user_id}` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Sharing** | `DELETE`| `/documents/{id}/permissions/{user_id}` | `owner`, `admin` | Document Owner only (`owner_id == user.id`) |
| **Admin** | `GET` | `/admin/audit-logs` | `admin` | Platform Admin only (`user.role == "admin"`) |

---

## 3. Detailed Endpoint Specifications

### 3.1 Authentication & Health

#### `POST /auth/register`
- **Description:** Registers a new user account. Role is hardcoded to `owner` on the server to prevent client-side privilege escalation.
- **Rate Limit:** 5 requests per 60 seconds per IP.
- **Request Body (JSON):**
  ```json
  {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "password": "Password123!"
  }
  ```
- **Validation Rules:**
  - `name`: String, 2 to 100 characters, non-blank.
  - `email`: Valid email format, automatically trimmed and lowercased.
  - `password`: String, 8 to 128 characters; requires at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character.
- **Responses:**
  - `201 Created`: Returns created user object (`id`, `name`, `email`, `role: "owner"`, `is_active: true`).
  - `409 Conflict`: Account with this email already exists.
  - `422 Unprocessable Entity`: Validation failure on input schema.
  - `429 Too Many Requests`: Rate limit exceeded.

#### `POST /auth/login`
- **Description:** Authenticates user credentials and issues an HMAC-SHA256 JWT access token.
- **Rate Limit:** 10 requests per 60 seconds per IP.
- **Request Format:** `application/x-www-form-urlencoded` (OAuth2 standard: `username` and `password`).
- **Responses:**
  - `200 OK`: Returns `{"access_token": "<jwt>", "token_type": "bearer"}`.
  - `401 Unauthorized`: Incorrect email/password, or account is deactivated.
  - `429 Too Many Requests`: Rate limit exceeded.

#### `GET /auth/me`
- **Description:** Retrieves the authenticated caller's profile.
- **Authentication:** `Authorization: Bearer <access_token>`.
- **Responses:**
  - `200 OK`: Returns `UserResponse` (`id`, `name`, `email`, `role`, `is_active`).
  - `401 Unauthorized`: Missing, expired, or invalid token.

#### `GET /health`
- **Description:** Simple service health check.
- **Responses:**
  - `200 OK`: `{"status": "ok"}`.

---

### 3.2 User Directory & Search

#### `GET /users/search`
- **Description:** Search active employees by name or email for document sharing.
- **Authentication:** Bearer JWT. Permitted for `owner` and `admin` roles.
- **Rate Limit:** 30 requests per 60 seconds.
- **Query Parameters:**
  - `q` (string, required, length 1–100): Search term matching name or email prefix/infix.
  - `limit` (integer, optional, default: 10, range: 1–50): Maximum results to return.
- **Security Guarantees:** Excludes the caller (`id != user.id`); excludes inactive users; returns minimal fields (`id`, `name`, `email`, `role`) with zero credential hashes.
- **Responses:**
  - `200 OK`: Array of `UserSearchResult` objects.
  - `401 Unauthorized`: Missing or invalid token.
  - `403 Forbidden`: Caller has `viewer` role.
  - `429 Too Many Requests`: Rate limit exceeded.

---

### 3.3 Document Lifecycle & Storage

#### `POST /documents/upload`
- **Description:** Uploads a document file and creates its database record. Creator becomes document owner.
- **Authentication:** Bearer JWT. Permitted for `owner` and `admin` roles.
- **Rate Limit:** 30 requests per 60 seconds.
- **Request Format:** `multipart/form-data`:
  - `file` (UploadFile, required): File binary (PDF, TXT, PNG, JPG; max 10 MB).
  - `title` (string, optional, max 200 chars): Display title (defaults to filename).
  - `description` (string, optional, max 5000 chars): Document description.
  - `category` (string, optional, max 100 chars): Category tag.
- **Responses:**
  - `201 Created`: Returns `DocumentResponse`.
  - `401 Unauthorized`: Missing or invalid token.
  - `403 Forbidden`: User has `viewer` role.
  - `413 Payload Too Large`: File exceeds 10 MB limit.
  - `415 Unsupported Media Type`: Invalid extension, mismatched MIME type, bad signature, or invalid UTF-8.
  - `429 Too Many Requests`: Rate limit exceeded.

#### `GET /documents`
- **Description:** Lists documents accessible to the caller (owned documents plus shared documents).
- **Authentication:** Bearer JWT.
- **Query Parameters:**
  - `search` (string, optional, max 200 chars): Matches title or filename.
  - `owner_id` (integer, optional): Filters by specific owner ID.
  - `owner_search` (string, optional, max 100 chars): Matches owner name or email.
  - `category` (string, optional, max 100 chars): Filters by category.
  - `date_from` (ISO date, optional): Filter start date (`YYYY-MM-DD`).
  - `date_to` (ISO date, optional): Filter end date (`YYYY-MM-DD`).
  - `limit` (integer, optional, 1–100): Pagination limit.
  - `offset` (integer, optional, >= 0): Pagination offset.
- **Security Guarantee:** Filters are applied strictly within the caller's access-control scope. Searching by an unshared `owner_id` returns an empty array, never disclosing unauthorized records.
- **Responses:**
  - `200 OK`: Array of `DocumentResponse` objects with `user_permission` annotation (`"owner"`, `"read"`, `"edit"`).
  - `422 Unprocessable Entity`: Invalid date range (`date_from > date_to`).

#### `GET /documents/{document_id}`
- **Description:** Retrieves metadata for a specific document.
- **Authentication:** Bearer JWT. Caller must be owner or hold `read`/`edit` permission.
- **Responses:**
  - `200 OK`: Returns `DocumentResponse`.
  - `404 Not Found`: Document nonexistent or caller lacks permission (prevents ID enumeration).

#### `PATCH /documents/{document_id}`
- **Description:** Updates document metadata (title, description, category).
- **Authentication:** Bearer JWT. Caller must be owner or hold `edit` permission.
- **Request Body (JSON):** At least one of `title`, `description`, `category`.
- **Responses:**
  - `200 OK`: Returns updated `DocumentResponse`.
  - `404 Not Found`: Inaccessible document or caller has `read`-only permission.
  - `422 Unprocessable Entity`: Empty update payload.

#### `DELETE /documents/{document_id}`
- **Description:** Deletes a document and its private storage file.
- **Authentication:** Bearer JWT. Restricted to the **Document Owner** (`owner_id == user.id`).
- **Security Behavior:** Historical audit logs retain the integer `document_id` via decoupled foreign key. If audit persistence fails, deletion transaction is rolled back.
- **Responses:**
  - `204 No Content`: Successfully deleted.
  - `404 Not Found`: Inaccessible document or caller is not owner.

#### `GET /documents/{document_id}/view`
- **Description:** Streams document content for in-browser viewing with security headers.
- **Authentication:** Bearer JWT. Caller must be owner or hold `read`/`edit` permission.
- **Security Headers Emitted:**
  - `X-Content-Type-Options: nosniff`
  - `Cache-Control: private, no-store, must-revalidate`
  - `X-Frame-Options: SAMEORIGIN`
  - `Content-Security-Policy: frame-ancestors 'self'`
- **Responses:**
  - `200 OK`: Binary stream (`inline` Content-Disposition).
  - `404 Not Found`: Inaccessible document or missing file.

#### `GET /documents/{document_id}/download`
- **Description:** Downloads document file. Enforces watermark policy based on caller identity:
  - **Owner:** Downloads original bit-for-bit file from storage (`attachment`).
  - **Shared Viewer (`read` or `edit`):** Downloads dynamically stamped PDF with viewer name, email, UTC timestamp, document ID, and trace reference.
  - **Non-PDF Shared Download:** Fails closed with HTTP 422 (watermarking is PDF-specific).
- **Rate Limit:** 30 requests per 60 seconds.
- **Responses:**
  - `200 OK`: Binary download (`attachment` Content-Disposition).
  - `404 Not Found`: Inaccessible document or caller lacks grant.
  - `422 Unprocessable Entity`: Corrupt/encrypted PDF, or shared download attempted on non-PDF.

#### `GET /documents/{document_id}/activity`
- **Description:** Retrieves activity and download history for a document.
- **Authentication:** Bearer JWT. Restricted to the **Document Owner**.
- **Responses:**
  - `200 OK`: `DocumentActivityResponse` containing list of activity events with actor name, email, action, and timestamp.
  - `404 Not Found`: Document nonexistent or caller is not owner.

---

### 3.4 Access Control & Sharing

#### `GET /documents/{document_id}/permissions`
- **Description:** Lists all active permission grants on a document. Restricted to the Document Owner.
- **Responses:**
  - `200 OK`: Array of `DocumentPermissionDetailResponse` objects (`id`, `user_id`, `user_name`, `user_email`, `permission_type`, `created_at`).
  - `404 Not Found`: Inaccessible document or caller is not owner.

#### `GET /documents/{document_id}/permissions/bulk-summary`
- **Description:** Calculates eligible active employee counts for bulk sharing without executing grants. Restricted to the Document Owner.
- **Responses:**
  - `200 OK`: `BulkSummaryResponse` (`eligible_count`, `new_grant_count`, `existing_grant_count`).
  - `404 Not Found`: Caller is not owner.

#### `POST /documents/{document_id}/permissions/bulk`
- **Description:** Shares document with all active employees in a single atomic transaction. Restricted to the Document Owner.
- **Request Body (JSON):** `{"permission_type": "read" | "edit"}`.
- **Responses:**
  - `200 OK`: `BulkPermissionResponse` (`document_id`, `permission_type`, `affected_count`).
  - `404 Not Found`: Caller is not owner.

#### `DELETE /documents/{document_id}/permissions/bulk`
- **Description:** Revokes all shared permissions in a single atomic transaction. Restricted to the Document Owner.
- **Responses:**
  - `200 OK`: `BulkRevokeResponse` (`document_id`, `revoked_count`).
  - `404 Not Found`: Caller is not owner.

#### `PUT /documents/{document_id}/permissions/{user_id}`
- **Description:** Grants or updates `read` or `edit` permission for a specific user. Restricted to the Document Owner.
- **Request Body (JSON):** `{"permission_type": "read" | "edit"}`.
- **Responses:**
  - `200 OK`: `PermissionResponse` (`document_id`, `user_id`, `permission_type`).
  - `400 Bad Request`: Owner attempted to grant access to themselves.
  - `404 Not Found`: Target user not found or inactive; or caller is not owner.

#### `DELETE /documents/{document_id}/permissions/{user_id}`
- **Description:** Immediately revokes access for a specific user. Restricted to the Document Owner.
- **Responses:**
  - `204 No Content`: Permission successfully revoked.
  - `404 Not Found`: No permission grant exists, or caller is not owner.

---

### 3.5 Administrative Audit Inspection

#### `GET /admin/audit-logs`
- **Description:** Retrieves paginated immutable audit logs with filtering. Restricted to the **Platform Administrator** (`user.role == "admin"`).
- **Authentication:** Bearer JWT with `admin` role. Non-admins receive HTTP 403 (audited as denial).
- **Query Parameters:**
  - `action` (string, optional, max 50 chars): Filters by specific action.
  - `outcome` (string, optional): Filters by `"success"`, `"denied"`, or `"failure"`.
  - `actor_id` (integer, optional, >= 1): Filters by actor user ID.
  - `document_id` (integer, optional, >= 1): Filters by historical document ID.
  - `start_date` (ISO datetime, optional): Earliest event timestamp.
  - `end_date` (ISO datetime, optional): Latest event timestamp.
  - `limit` (integer, optional, default: 50, range: 1–100): Bounded limit preventing table-scan DoS.
  - `offset` (integer, optional, default: 0, >= 0): Result offset.
- **Responses:**
  - `200 OK`: `{"items": [...], "limit": 50, "offset": 0}` with explicit fields (`id`, `actor_id`, `document_id`, `action`, `outcome`, `details`, `created_at`).
  - `401 Unauthorized`: Unauthenticated request.
  - `403 Forbidden`: Caller does not have `admin` role.
  - `422 Unprocessable Entity`: Invalid outcome or invalid date range (`start_date > end_date`).
