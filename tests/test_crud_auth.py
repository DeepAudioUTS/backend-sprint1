"""Tests for app/crud/auth.py — password hashing and user authentication."""

from sqlalchemy.orm import Session

from app.crud.auth import authenticate_user, get_user_by_email, hash_password, verify_password
from app.models.user import User


# --- Password helpers ---

def test_hash_password_differs_from_plaintext() -> None:
    assert hash_password("secret") != "secret"


def test_verify_password_correct() -> None:
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True


def test_verify_password_incorrect() -> None:
    hashed = hash_password("secret")
    assert verify_password("wrong", hashed) is False


# --- get_user_by_email ---

def test_get_user_by_email_returns_user(db: Session, test_user: User) -> None:
    result = get_user_by_email(db, test_user.email)
    assert result is not None
    assert result.id == test_user.id


def test_get_user_by_email_not_found_returns_none(db: Session) -> None:
    assert get_user_by_email(db, "nobody@example.com") is None


# --- authenticate_user ---

def test_authenticate_user_success(db: Session, test_user: User) -> None:
    result = authenticate_user(db, test_user.email, "testpassword")
    assert result is not None
    assert result.id == test_user.id


def test_authenticate_user_wrong_password_returns_none(db: Session, test_user: User) -> None:
    assert authenticate_user(db, test_user.email, "wrongpassword") is None


def test_authenticate_user_unknown_email_returns_none(db: Session) -> None:
    assert authenticate_user(db, "nobody@example.com", "password") is None
