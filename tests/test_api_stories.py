"""Tests for GET/POST /api/v1/stories/ and GET /api/v1/stories/{story_id}."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import Child
from app.models.story import Story, StoryStatus
from app.models.user import User


# --- GET /api/v1/stories/ ---

def test_get_stories_empty(client: TestClient, test_user: User, auth_headers: dict) -> None:
    response = client.get("/api/v1/stories/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert "limit" in data
    assert "offset" in data


def test_get_stories_returns_user_stories(
    client: TestClient, db: Session, test_user: User, test_child: Child, auth_headers: dict
) -> None:
    db.add(Story(child_id=test_child.id, theme="space", status=StoryStatus.COMPLETED))
    db.commit()

    response = client.get("/api/v1/stories/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["theme"] == "space"


def test_get_stories_pagination_params_reflected(
    client: TestClient, test_user: User, auth_headers: dict
) -> None:
    response = client.get("/api/v1/stories/?limit=5&offset=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 10


def test_get_stories_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/stories/")
    assert response.status_code == 401


def test_get_stories_invalid_limit_returns_422(
    client: TestClient, test_user: User, auth_headers: dict
) -> None:
    response = client.get("/api/v1/stories/?limit=0", headers=auth_headers)
    assert response.status_code == 422


# --- POST /api/v1/stories/ ---

def test_post_story_creates_with_generating_text(
    client: TestClient, test_child: Child, auth_headers: dict
) -> None:
    response = client.post(
        "/api/v1/stories/",
        json={"child_id": str(test_child.id), "theme": "dinosaurs"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["theme"] == "dinosaurs"
    assert data["status"] == "generating_text"
    assert data["child_id"] == str(test_child.id)
    assert data["title"] is None
    assert data["content"] is None
    assert data["audio_url"] is None


def test_post_story_unauthenticated_returns_401(client: TestClient, test_child: Child) -> None:
    response = client.post(
        "/api/v1/stories/",
        json={"child_id": str(test_child.id), "theme": "ocean"},
    )
    assert response.status_code == 401


def test_post_story_missing_fields_returns_422(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post("/api/v1/stories/", json={}, headers=auth_headers)
    assert response.status_code == 422


# --- GET /api/v1/stories/{story_id} ---

def test_get_story_by_id_returns_story(
    client: TestClient, db: Session, test_user: User, test_child: Child, auth_headers: dict
) -> None:
    story = Story(
        child_id=test_child.id,
        theme="ocean",
        title="Ocean Tale",
        status=StoryStatus.COMPLETED,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    response = client.get(f"/api/v1/stories/{story.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(story.id)
    assert data["title"] == "Ocean Tale"


def test_get_story_by_id_not_found_returns_404(
    client: TestClient, test_user: User, auth_headers: dict
) -> None:
    response = client.get(f"/api/v1/stories/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_get_story_by_id_unauthenticated_returns_401(
    client: TestClient, db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="theme", status=StoryStatus.GENERATING_TEXT)
    db.add(story)
    db.commit()
    db.refresh(story)

    response = client.get(f"/api/v1/stories/{story.id}")
    assert response.status_code == 401
