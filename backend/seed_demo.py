from getpass import getpass
import os

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


DEMO_USERS = [
    ("TrustVault Admin", "admin@example.com", "admin"),
    ("TrustVault Owner", "owner@example.com", "owner"),
    ("TrustVault Viewer", "viewer@example.com", "viewer"),
]


def seed_demo_accounts(db=None):
    """
    Seed initial demo accounts safely.

    Schema creation is managed via Alembic migrations, never create_all().
    Rerunning this script preserves existing passwords, roles, and active statuses.
    """
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        existing_users = {
            user.email: user
            for user in db.scalars(
                select(User).where(
                    User.email.in_([email for _, email, _ in DEMO_USERS])
                )
            ).all()
        }

        users_to_create = [
            (name, email, role)
            for name, email, role in DEMO_USERS
            if email not in existing_users
        ]

        if not users_to_create:
            print("All demo accounts already exist. No accounts were modified.")
            for _, email, _ in DEMO_USERS:
                existing = existing_users[email]
                print(
                    f" - {email} (role: {existing.role}, active: {existing.is_active}) - skipped"
                )
            return 0

        for _, email, _ in DEMO_USERS:
            if email in existing_users:
                existing = existing_users[email]
                print(
                    f"Demo account {email} already exists (role: {existing.role}, active: {existing.is_active}); skipping."
                )

        passwords = {}
        for name, email, role in users_to_create:
            # Check for environment variable (useful for automated testing or unattended setup)
            env_var = f"DEMO_PASSWORD_{role.upper()}"
            env_pwd = os.getenv(env_var)
            if env_pwd and len(env_pwd) >= 12:
                passwords[email] = env_pwd
                continue

            while True:
                password = getpass(f"Set password for {email} ({role}): ")
                if len(password) < 12:
                    print("Use at least 12 characters.")
                    continue

                confirmation = getpass("Confirm password: ")
                if password != confirmation:
                    print("Passwords do not match.")
                    continue

                passwords[email] = password
                break

        for name, email, role in users_to_create:
            user = User(
                name=name,
                email=email,
                password_hash=hash_password(passwords[email]),
                role=role,
                is_active=True,
            )
            db.add(user)

        db.commit()
        print(f"\nSuccessfully seeded {len(users_to_create)} demo account(s).")
        return len(users_to_create)

    finally:
        if owns_session:
            db.close()


def main():
    seed_demo_accounts()


if __name__ == "__main__":
    main()
