"""Tests for app/crud/child.py — child retrieval by user."""

import uuid

from sqlalchemy.orm import Session

from app.crud.child import get_children_by_user_id
from app.crud.auth import hash_password
from app.models.child import Child
from app.models.user import User


def test_get_children_returns_correct_children(
    db: Session, test_user: User, test_child: Child
) -> None:
    result = get_children_by_user_id(db, test_user.id)
    assert len(result) == 1
    assert result[0].id == test_child.id
    assert result[0].name == test_child.name
    assert result[0].age == test_child.age


def test_get_children_empty_for_unknown_user(db: Session) -> None:
    result = get_children_by_user_id(db, uuid.uuid4())
    assert result == []


def test_get_children_does_not_include_other_users_children(
    db: Session, test_user: User, test_child: Child
) -> None:
    other_user = User(
        name="Other",
        email="other@example.com",
        hashed_password=hash_password("pass"),
        subscription_plan="free",
    )
    db.add(other_user)
    db.flush()
    db.add(Child(user_id=other_user.id, name="Other Child", age=4))
    db.commit()

    result = get_children_by_user_id(db, test_user.id)
    assert len(result) == 1
    assert result[0].id == test_child.id


def test_get_children_returns_multiple_children(db: Session, test_user: User) -> None:
    db.add(Child(user_id=test_user.id, name="Alice", age=5))
    db.add(Child(user_id=test_user.id, name="Bob", age=8))
    db.commit()

    result = get_children_by_user_id(db, test_user.id)
    assert len(result) == 2
