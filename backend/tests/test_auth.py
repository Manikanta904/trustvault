
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, User
from app.security import create_access_token, hash_password
from datetime import datetime, timedelta, timezone
import jwt

client = TestClient(app)

TEST_PASSWORD = "TestPassword!9382"


def create_test_user():
    """Create a uniquely named test user without deleting audit history."""
    email = f"trustvault-test-{uuid4().hex}@example.com"

    with SessionLocal() as db:
        user = User(
            name="Test Owner",
            email=email,
            password_hash=hash_password(TEST_PASSWORD),
            role="owner",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "id": user.id,
            "email": user.email,
            "token": create_access_token(user),
        }


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_requires_authentication():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_login_and_get_current_user():
    test_user = create_test_user()

    response = client.post(
        "/auth/login",
        data={
            "username": test_user["email"],
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == test_user["email"]
    assert response.json()["role"] == "owner"
    assert "password_hash" not in response.json()


def test_invalid_password_is_rejected():
    test_user = create_test_user()

    response = client.post(
        "/auth/login",
        data={
            "username": test_user["email"],
            "password": "WrongPassword!123",
        },
    )

    assert response.status_code == 401

    # Verify that the failed login was audited.
    with SessionLocal() as db:
        audit_entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.actor_id == test_user["id"],
                AuditLog.action == "login",
                AuditLog.outcome == "denied",
                AuditLog.details
                == "Invalid credentials or inactive account",
            )
            .order_by(AuditLog.id.desc())
            .first()
        )

        assert audit_entry is not None


def test_unknown_user_is_rejected():
    email = f"unknown-{uuid4().hex}@example.com"

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "SomePassword!123",
        },
    )

    assert response.status_code == 401


def test_deactivated_user_cannot_use_existing_token():
    test_user = create_test_user()

    with SessionLocal() as db:
        user = db.get(User, test_user["id"])

        assert user is not None
        user.is_active = False
        db.commit()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )

    assert response.status_code == 401



def test_expired_token_with_access_token_helper_is_rejected():
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.security import JWT_SECRET

    test_user = create_test_user()
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    expired_token = jwt.encode(
        {
            "sub": str(test_user["id"]),
            "role": "owner",
            "iat": expired_time - timedelta(minutes=5),
            "exp": expired_time,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_expired_jwt_is_rejected():
    test_user = create_test_user()

    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    payload = {
        "sub": str(test_user["id"]),
        "role": "owner",
        "iat": expired_time - timedelta(minutes=5),
        "exp": expired_time,
    }

    expired_token = jwt.encode(
        payload,
        __import__("app.security", fromlist=["JWT_SECRET"]).JWT_SECRET,
        algorithm="HS256",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_demo_accounts_authentication_and_roles():
    """Verify Admin, Owner, and Viewer demo accounts authenticate and have correct roles."""
    from seed_demo import seed_demo_accounts, DEMO_USERS, DEFAULT_DEMO_PASSWORD

    # Ensure demo accounts are seeded with standard credentials
    with SessionLocal() as db:
        seed_demo_accounts(db=db, sync_credentials=True)

    expected_accounts = [
        ("admin@example.com", "admin"),
        ("owner@example.com", "owner"),
        ("viewer@example.com", "viewer"),
    ]

    for email, role in expected_accounts:
        # 1. Correct credentials succeed
        login_res = client.post(
            "/auth/login",
            data={
                "username": email,
                "password": DEFAULT_DEMO_PASSWORD,
            },
        )
        assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
        token = login_res.json()["access_token"]

        # 2. /auth/me returns the verified role
        me_res = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        user_info = me_res.json()
        assert user_info["email"] == email
        assert user_info["role"] == role
        assert user_info["is_active"] is True

        # 3. Incorrect password is rejected
        bad_res = client.post(
            "/auth/login",
            data={
                "username": email,
                "password": "wrongpassword!123",
            },
        )
        assert bad_res.status_code == 401


def test_demo_accounts_seed_synchronization_and_rerun_safety():
    """Verify demo seed idempotency and explicit credential synchronization."""
    from seed_demo import seed_demo_accounts, DEMO_USERS, DEFAULT_DEMO_PASSWORD
    from sqlalchemy import select

    with SessionLocal() as db:
        # First ensure demo accounts exist
        seed_demo_accounts(db=db, sync_credentials=True)

        # Record state
        users_before = {
            u.email: (u.password_hash, u.role, u.is_active)
            for u in db.scalars(
                select(User).where(User.email.in_([e for _, e, _ in DEMO_USERS]))
            ).all()
        }

        # Safe rerun without sync_credentials should skip and return 0
        rerun_count = seed_demo_accounts(db=db, sync_credentials=False)
        assert rerun_count == 0

        # State must not be modified
        users_after = {
            u.email: (u.password_hash, u.role, u.is_active)
            for u in db.scalars(
                select(User).where(User.email.in_([e for _, e, _ in DEMO_USERS]))
            ).all()
        }
        assert users_before == users_after

        # Explicit synchronization should return total demo users count
        sync_count = seed_demo_accounts(db=db, sync_credentials=True)
        assert sync_count == len(DEMO_USERS)

