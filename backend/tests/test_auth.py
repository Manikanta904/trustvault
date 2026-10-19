
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import User
from app.security import hash_password

client = TestClient(app)

TEST_EMAIL = "trustvault-test@example.com"
TEST_PASSWORD = "TestPassword!9382"


def create_test_user():
    with SessionLocal() as db:
        db.execute(
            delete(User).where(User.email == TEST_EMAIL)
        )

        db.add(
            User(
                name="Test Owner",
                email=TEST_EMAIL,
                password_hash=hash_password(TEST_PASSWORD),
                role="owner",
                is_active=True,
            )
        )
        db.commit()


def remove_test_user():
    with SessionLocal() as db:
        db.execute(
            delete(User).where(User.email == TEST_EMAIL)
        )
        db.commit()


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_requires_authentication():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_login_and_get_current_user():
    create_test_user()

    try:
        response = client.post(
            "/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

        assert response.status_code == 200

        token = response.json()["access_token"]

        response = client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}"
            },
        )

        assert response.status_code == 200
        assert response.json()["email"] == TEST_EMAIL
        assert response.json()["role"] == "owner"
        assert "password_hash" not in response.json()

    finally:
        remove_test_user()


def test_invalid_password_is_rejected():
    create_test_user()

    try:
        response = client.post(
            "/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": "WrongPassword!123",
            },
        )

        assert response.status_code == 401

    finally:
        remove_test_user()


def test_unknown_user_is_rejected():
    response = client.post(
        "/auth/login",
        data={
            "username": "unknown@example.com",
            "password": "SomePassword!123",
        },
    )

    assert response.status_code == 401
