# TrustVault — AI Development Log

## Entry 1 — 2026-10-19 — Backend foundation and authentication

**AI tools used:** ChatGPT; VS Code for implementation and testing. Add Antigravity only if actually used.

**Objective:** Build the initial FastAPI backend with user authentication, role identification and automated tests.

**Prompt / request:** I asked for a step-by-step implementation of the TrustVault backend, including SQLAlchemy database configuration, a user model with administrator, owner and viewer roles, Argon2 password hashing, JWT authentication, login and current-user endpoints, demo-account seeding, and pytest tests.

**AI output:** The implementation included `app/database.py`, `app/models.py`, `app/security.py`, `app/main.py`, `seed_demo.py`, and `tests/test_auth.py`. It configured SQLite for local development and created the three demo accounts.

**What I verified:**
- The FastAPI server started successfully.
- Swagger UI opened and the health endpoint returned a successful response.
- Administrator, owner and viewer accounts were created with their expected roles.
- `python -m pytest -v` completed with 5 tests passed.
- The tests covered the health endpoint, unauthenticated access to the current-user endpoint, successful login, invalid passwords and unknown users.

**Specific issue identified:** The initial automated tests use the configured development database rather than a dedicated isolated test database. This creates a risk of test data interfering with development data.

**Correction / follow-up:** The tests passed, but the database-isolation improvement is not yet implemented. I will create an isolated test database before expanding the security-critical document APIs. I also observed a Starlette TestClient/httpx deprecation warning; it did not cause any test failures and requires a separate dependency-compatibility review.

**Security review:** Authentication is implemented, but per-document authorization has not yet been implemented. A valid login must not be treated as permission to access every document.

**Commit:** Add the actual Git commit URL after committing this milestone.

**Status:** Initial authentication milestone completed; document-security requirements remain in progress.

## Entry 2 — 2026-10-19 — Document authorization, file storage and API tests

**AI tools used:** ChatGPT; VS Code and local terminal for implementation and verification.

**Objective:** Extend the FastAPI backend with document-level permissions, private file uploads and downloads, permission grant/revocation, audit logging and automated authorization tests.

**Prompt / request:** Review the current TrustVault implementation and test results, identify security gaps in document authorization and file storage, and guide the next steps for documenting the work, committing the changes and testing the API through Swagger UI.

**AI-assisted implementation reviewed:** The current code includes document routes, an authorization helper, an audit helper, file-storage utilities, document and permission schemas, database models and an Alembic migration. The file-storage code uses generated storage keys, a 10 MB size limit, extension/content-type checks and basic file-signature validation.

**Verification performed:**
- Ran `python -m pytest -v` from the backend directory.
- Result: **17 passed, 1 warning in 3.80 seconds**.
- Tests covered authentication, owner access, denied access without grants, read versus edit permissions, admin access without a grant, permission revocation, missing documents, unauthenticated endpoints, viewer restrictions, and an upload/download/grant/revoke workflow.
- Ran `git diff --check`; it produced no errors.
- Inspected `.gitignore`, `backend/app/file_storage.py`, `backend/app/routers/documents.py`, `backend/app/audit.py`, `backend/app/main.py` and the existing `PROMPTS.md`.

**Specific warning observed:** Starlette emitted a deprecation warning concerning use of `httpx` with `starlette.testclient`. The warning did not cause the tests to fail.

**Security findings and follow-up:**
- The file-storage implementation checks file size, allowed extensions, content type and basic signatures. These checks do not replace comprehensive file-content validation.
- Document authorization is checked by the document routes; cross-user and revocation tests passed.
- Audit entries are added to the SQLAlchemy session and depend on the endpoint transaction being committed.
- Failed login attempts and some upload-validation failures do not appear to be audited consistently.
- The current test suite uses the configured development database; isolated test-database setup remains a follow-up.
- Swagger UI still needs a live end-to-end check, including unauthorized download attempts and access after permission revocation.

**Corrections made during this milestone:** The current test suite includes additional coverage for viewer restrictions and the upload/download/grant/revoke workflow. Record any further code corrections here after they are actually implemented and verified.

**Commit:** Add the real commit hash and repository URL after committing this milestone. Do not invent a commit reference.

**Status:** Backend authorization and file-handling implementation passes 17 automated tests. Further audit coverage, live Swagger verification, threat-model documentation and deployment checks remain outstanding.