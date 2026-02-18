"""Bootstrap admin provisioning tests."""

import logging

from sqlalchemy.orm import Session

from app.bootstrap import ensure_bootstrap_admin
from app.models import User, UserRole


def _get_user(db_session: Session, email: str) -> User | None:
    """Fetch user by email."""
    return db_session.query(User).filter(User.email == email).first()


def test_bootstrap_creates_admin_user(monkeypatch, db_session: Session) -> None:
    """Bootstrap routine should create an admin user when missing."""
    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_ENABLED", True)
    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_EMAIL", "seed-admin@example.com")
    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_PASSWORD", "SeedPass123")

    ensure_bootstrap_admin(logging.getLogger("test.bootstrap"))

    user = _get_user(db_session, "seed-admin@example.com")
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.hashed_password != "SeedPass123"


def test_bootstrap_promotes_existing_user_to_admin(monkeypatch, db_session: Session) -> None:
    """Bootstrap routine should upgrade existing user role and activation."""
    user = User(
        email="existing-user@example.com",
        hashed_password="already-hashed",
        role=UserRole.USER,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_ENABLED", True)
    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_EMAIL", "existing-user@example.com")
    monkeypatch.setattr("app.bootstrap.settings.BOOTSTRAP_ADMIN_PASSWORD", "SeedPass123")

    ensure_bootstrap_admin(logging.getLogger("test.bootstrap"))

    db_session.refresh(user)
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.hashed_password == "already-hashed"

