
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import User

client = TestClient(app)

TEST_EMAIL = "trustvault-registration-test@example.com"
TEST_PASSWORD = "SecureTestPass!9382"


def remove_test_user():
    with SessionLocal() as db:
        db.execute(
            delete(User).where(User.email == TEST_EMAIL)
        )
        db.commit()


@pytest.fixture(autouse=True)
def clean_registration_test_user():
    remove_test_user()
    yield
    remove_test_user()


def register_user(payload=None):
    if payload is None:
        payload = {
            "name": "Registration Test",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        }

    return client.post("/auth/register", json=payload)


def test_registration_creates_owner():
    response = register_user()

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Registration Test"
    assert data["email"] == TEST_EMAIL
    assert data["role"] == "owner"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data

    with SessionLocal() as db:
        user = db.query(User).filter_by(email=TEST_EMAIL).one()
        assert user.password_hash != TEST_PASSWORD
        assert user.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected():
    first = register_user()
    second = register_user()

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "Valid User",
            "email": "not-an-email",
            "password": TEST_PASSWORD,
        },
        {
            "name": "Valid User",
            "email": TEST_EMAIL,
            "password": "short",
        },
        {
            "name": "   ",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    ],
)
def test_invalid_registration_input_is_rejected(payload):
    response = register_user(payload)

    assert response.status_code == 422


def test_registered_user_can_log_in():
    registration = register_user()
    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]


def test_client_cannot_register_as_admin():
    response = register_user(
        {
            "name": "Registration Test",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "role": "admin",
        }
    )

    assert response.status_code == 201
    assert response.json()["role"] == "owner"

    with SessionLocal() as db:
        user = db.query(User).filter_by(email=TEST_EMAIL).one()
        assert user.role == "owner"
