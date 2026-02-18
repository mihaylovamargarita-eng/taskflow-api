"""Pytest fixtures and test app wiring."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_taskflow.db"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_MINUTES"] = "10080"
os.environ["AUTO_CREATE_TABLES"] = "false"

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_taskflow.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def override_get_db() -> Generator[Session, None, None]:
    """Yield a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def reset_database() -> Generator[None, None, None]:
    """Reset database schema between tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(reset_database: None) -> Generator[TestClient, None, None]:
    """Return test client with DB dependency override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(reset_database: None) -> Generator[Session, None, None]:
    """Yield a writable test DB session for direct data setup in tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
