"""Shared pytest fixtures for all test modules.

Uses an in-memory SQLite database so tests run without a real PostgreSQL instance.
Each test function gets a fresh session; all rows are cleared after each test.
"""
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.crud.auth import hash_password
from app.db.database import Base, get_db
from app.main import app
from app.models.child import Child
from app.models.user import User

_DATABASE_URL = "sqlite://"

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_tables() -> Generator[None, Any, None]:
    """Create all tables once for the entire test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Provide a DB session and clean up all rows after each test."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture()
def client(db):
    """Provide a TestClient with the DB dependency overridden."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db) -> User:
    """Create and return a test user (password: testpassword)."""
    user = User(
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpassword"),
        subscription_plan="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def test_child(db, test_user) -> Child:
    """Create and return a child belonging to test_user."""
    child = Child(user_id=test_user.id, name="Emma", age=7)
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@pytest.fixture()
def auth_headers(test_user) -> dict[str, str]:
    """Return Authorization headers for test_user."""
    token = create_access_token(subject=test_user.email)
    return {"Authorization": f"Bearer {token}"}
