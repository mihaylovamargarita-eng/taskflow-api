"""Startup bootstrap routines for demo/admin provisioning."""

from __future__ import annotations

import logging

from app.auth import get_password_hash
from app.config import get_settings
from app.database import SessionLocal
from app.models import User, UserRole

settings = get_settings()


def ensure_bootstrap_admin(logger: logging.Logger) -> None:
    """Create or promote a bootstrap admin account when configured."""
    if not settings.BOOTSTRAP_ADMIN_ENABLED:
        return

    email = settings.BOOTSTRAP_ADMIN_EMAIL
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not email or not password:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_ENABLED=true requires BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD."
        )
    if len(password) < 8:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            logger.info("bootstrap_admin_created email=%s", email)
            return

        updated = False
        if user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN
            updated = True
        if not user.is_active:
            user.is_active = True
            updated = True

        if updated:
            db.add(user)
            db.commit()
            logger.info("bootstrap_admin_updated email=%s", email)
        else:
            logger.info("bootstrap_admin_exists email=%s", email)
    finally:
        db.close()

