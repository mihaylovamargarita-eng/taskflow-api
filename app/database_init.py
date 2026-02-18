"""Database initialization helpers."""

from app import models  # noqa: F401
from app.database import Base, engine


def init_db() -> None:
    """Create all database tables for registered SQLAlchemy models."""
    Base.metadata.create_all(bind=engine)

