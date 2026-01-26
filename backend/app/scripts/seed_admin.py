import os

from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.security import hash_password


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "change-me")

    session: Session = SessionLocal()
    try:
        user = session.query(models.User).filter(models.User.email == email).first()
        if user:
            user.password_hash = hash_password(password)
            user.role = models.Role.admin
            user.is_active = True
        else:
            user = models.User(
                email=email,
                password_hash=hash_password(password),
                role=models.Role.admin,
                is_active=True,
            )
            session.add(user)
        session.commit()
        print(f"Seeded admin user: {email}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
