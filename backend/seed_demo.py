import argparse
from getpass import getpass
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password

DEFAULT_DEMO_PASSWORD = "123456789abc"

DEMO_USERS = [
    ("TrustVault Admin", "admin@example.com", "admin"),
    ("TrustVault Owner", "owner@example.com", "owner"),
    ("TrustVault Viewer", "viewer@example.com", "viewer"),
]


def _resolve_password_for_role(role: str, email: str) -> str:
    """Resolve password from environment variable, prompt, or default demo password."""
    env_var = f"DEMO_PASSWORD_{role.upper()}"
    env_pwd = os.getenv(env_var) or os.getenv("DEMO_DEFAULT_PASSWORD")
    if env_pwd and len(env_pwd) >= 12:
        return env_pwd

    if sys.stdin and sys.stdin.isatty():
        try:
            pwd = getpass(
                f"Set password for {email} ({role}) [Enter for default demo password]: "
            )
            if not pwd:
                return DEFAULT_DEMO_PASSWORD
            if len(pwd) < 12:
                print("Password must be at least 12 characters. Using default demo password.")
                return DEFAULT_DEMO_PASSWORD
            confirmation = getpass("Confirm password: ")
            if pwd != confirmation:
                print("Passwords do not match. Using default demo password.")
                return DEFAULT_DEMO_PASSWORD
            return pwd
        except (EOFError, KeyboardInterrupt):
            print("\nDefaulting to standard demo password.")
            return DEFAULT_DEMO_PASSWORD

    return DEFAULT_DEMO_PASSWORD


def seed_demo_accounts(db=None, sync_credentials: bool = False):
    """
    Seed initial demo accounts safely.

    Schema creation is managed via Alembic migrations, never create_all().
    Rerunning this script preserves existing passwords, roles, and active statuses by default.
    If sync_credentials=True, explicitly synchronizes demo accounts to standard local-demo credentials.
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

        if sync_credentials:
            count = 0
            for name, email, role in DEMO_USERS:
                target_pwd = _resolve_password_for_role(role, email)
                if email in existing_users:
                    user = existing_users[email]
                    user.name = name
                    user.role = role
                    user.is_active = True
                    user.password_hash = hash_password(target_pwd)
                    print(f"Synchronized credentials for {email} ({role}).")
                else:
                    user = User(
                        name=name,
                        email=email,
                        password_hash=hash_password(target_pwd),
                        role=role,
                        is_active=True,
                    )
                    db.add(user)
                    print(f"Created demo account {email} ({role}).")
                count += 1
            db.commit()
            print(f"\nSuccessfully synchronized {count} demo account(s).")
            return count

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

        passwords = {
            email: _resolve_password_for_role(role, email)
            for name, email, role in users_to_create
        }

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
    parser = argparse.ArgumentParser(
        description="Seed or synchronize TrustVault demo accounts."
    )
    parser.add_argument(
        "--sync-credentials",
        action="store_true",
        help="Explicitly synchronize demo accounts to standard local-demo credentials.",
    )
    args = parser.parse_args()
    seed_demo_accounts(sync_credentials=args.sync_credentials)


if __name__ == "__main__":
    main()

