
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
