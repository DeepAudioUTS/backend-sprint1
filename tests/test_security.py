"""Tests for app/core/security.py — JWT token creation and decoding."""

from app.core.security import create_access_token, decode_access_token


def test_create_and_decode_token_roundtrip() -> None:
    token = create_access_token("user@example.com")
    assert decode_access_token(token) == "user@example.com"


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("not.a.valid.token") is None


def test_decode_empty_string_returns_none() -> None:
    assert decode_access_token("") is None


def test_tokens_for_different_subjects_are_different() -> None:
    token_a = create_access_token("a@example.com")
    token_b = create_access_token("b@example.com")
    assert token_a != token_b
