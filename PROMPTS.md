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