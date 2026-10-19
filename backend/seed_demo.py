
from getpass import getpass

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


DEMO_USERS = [
    ("TrustVault Admin", "admin@example.com", "admin"),
    ("TrustVault Owner", "owner@example.com", "owner"),
    ("TrustVault Viewer", "viewer@example.com", "viewer"),
]


def main():
    Base.metadata.create_all(bind=engine)

    passwords = {}

    for name, email, role in DEMO_USERS:
        while True:
            password = getpass(f"Set password for {email}: ")

            if len(password) < 12:
                print("Use at least 12 characters.")
                continue

            confirmation = getpass("Confirm password: ")

            if password != confirmation:
                print("Passwords do not match.")
                continue

            passwords[email] = password
            break

    with SessionLocal() as db:
        for name, email, role in DEMO_USERS:
            user = db.scalar(
                select(User).where(User.email == email)
            )

            if user is None:
                user = User(
                    name=name,
                    email=email,
                    password_hash=hash_password(passwords[email]),
                    role=role,
                    is_active=True,
                )
                db.add(user)
            else:
                user.name = name
                user.role = role
                user.password_hash = hash_password(passwords[email])
                user.is_active = True

        db.commit()

    print("\nDemo accounts created or updated successfully.")


if __name__ == "__main__":
    main()
