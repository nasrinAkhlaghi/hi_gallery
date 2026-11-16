"""Explicit local-development setup: create an Admin and missing sample categories."""

import argparse
from datetime import datetime, timezone
from getpass import getpass
from uuid import uuid4

from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Account, Admin, Category
from app.db.session import SessionLocal
from app.modules.auth.security import hash_password

SAMPLE_CATEGORIES = [("Ceramics", "ceramics"), ("Textiles", "textiles"), ("Jewelry", "jewelry"), ("Home objects", "home-objects")]


def seed(session: Session, email: str, password: str) -> None:
    if get_settings().environment != "development":
        raise ValueError("Development seed requires ENVIRONMENT=development")
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    account = session.scalar(select(Account).where(Account.email == email))
    if account is not None and (account.admin is None or account.admin.status != "ACTIVE" or account.status != "ACTIVE"):
        raise ValueError("This email already belongs to another or inactive account; use a new email")
    now = datetime.now(timezone.utc)
    if account is None:
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must contain 12–128 characters")
        account = Account(id=uuid4(), email=email, password_hash=hash_password(password), status="ACTIVE", created_at=now, updated_at=now)
        session.add(account)
        session.flush()
        session.add(Admin(id=uuid4(), account_id=account.id, display_name="Local Admin", status="ACTIVE", created_at=now, updated_at=now))
    for name, slug in SAMPLE_CATEGORIES:
        if session.scalar(select(Category.id).where(Category.slug == slug)) is None:
            session.add(Category(id=uuid4(), name=name, slug=slug, status="ACTIVE", created_at=now, updated_at=now))
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-email", default="local-admin@example.com")
    args = parser.parse_args()
    if get_settings().environment != "development":
        parser.error("Development seed requires ENVIRONMENT=development")
    password = getpass("New local Admin password (12–128 characters; existing password stays unchanged): ")
    with SessionLocal() as session:
        try:
            seed(session, args.admin_email, password)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"Local Admin ready: {args.admin_email}. Sample categories are ready. Existing records/passwords were preserved.")


if __name__ == "__main__":
    main()
