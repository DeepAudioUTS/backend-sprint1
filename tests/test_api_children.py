"""Tests for GET /api/v1/children/."""

from fastapi.testclient import TestClient

from app.models.child import Child
from app.models.user import User


def test_get_children_returns_list(
    client: TestClient, test_user: User, test_child: Child, auth_headers: dict
) -> None:
    response = client.get("/api/v1/children/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == test_child.name
    assert data[0]["age"] == test_child.age


def test_get_children_empty_when_no_children(
    client: TestClient, test_user: User, auth_headers: dict
) -> None:
    response = client.get("/api/v1/children/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_children_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/children/")
    assert response.status_code == 401


def test_get_children_response_has_expected_fields(
    client: TestClient, test_user: User, test_child: Child, auth_headers: dict
) -> None:
    response = client.get("/api/v1/children/", headers=auth_headers)
    item = response.json()[0]
    assert "id" in item
    assert "user_id" in item
    assert "name" in item
    assert "age" in item
    assert "created_at" in item
    assert "updated_at" in item
