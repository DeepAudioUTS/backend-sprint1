"""Tests for /api/v1/stories/ endpoints."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.child import Child
from app.models.story import Story
from app.models.story_draft import StoryDraft, DraftStatus
from app.models.user import User


# --- GET /api/v1/stories/ ---

def test_get_stories_empty(client: TestClient, test_user: User, auth_headers: dict) -> None:
    response = client.get("/api/v1/stories/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_get_stories_returns_completed_stories(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    db.add(Story(child_id=test_child.id, theme="space"))
    db.commit()

    response = client.get("/api/v1/stories/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["theme"] == "space"


def test_get_stories_response_has_no_status_field(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    db.add(Story(child_id=test_child.id, theme="jungle"))
    db.commit()

    response = client.get("/api/v1/stories/", headers=auth_headers)
    assert "status" not in response.json()["items"][0]


def test_get_stories_pagination_params_reflected(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.get("/api/v1/stories/?limit=5&offset=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 10


def test_get_stories_unauthenticated_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/stories/").status_code == 401


def test_get_stories_invalid_limit_returns_422(
    client: TestClient, auth_headers: dict
) -> None:
    assert client.get("/api/v1/stories/?limit=0", headers=auth_headers).status_code == 422


# --- POST /api/v1/stories/ ---

def test_post_story_creates_draft_only(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    with patch("app.api.v1.stories.generate_abstract_background"):
        response = client.post(
            "/api/v1/stories/",
            json={"child_id": str(test_child.id), "theme": "dinosaurs"},
            headers=auth_headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert "draft_id" in data
    assert data["status"] == DraftStatus.GENERATING_ABSTRACT

    # No Story record yet
    stories = db.scalars(select(Story).where(Story.child_id == test_child.id)).all()
    assert len(stories) == 0

    draft = db.scalars(
        select(StoryDraft).where(StoryDraft.child_id == test_child.id)
    ).first()
    assert draft is not None
    assert draft.theme == "dinosaurs"


def test_post_story_triggers_abstract_background_task(
    client: TestClient, test_child: Child, auth_headers: dict
) -> None:
    with patch("app.api.v1.stories.generate_abstract_background") as mock_bg:
        client.post(
            "/api/v1/stories/",
            json={"child_id": str(test_child.id), "theme": "dinosaurs"},
            headers=auth_headers,
        )
    mock_bg.assert_called_once()


def test_post_story_unauthenticated_returns_401(client: TestClient, test_child: Child) -> None:
    response = client.post(
        "/api/v1/stories/",
        json={"child_id": str(test_child.id), "theme": "ocean"},
    )
    assert response.status_code == 401


def test_post_story_missing_fields_returns_422(client: TestClient, auth_headers: dict) -> None:
    assert client.post("/api/v1/stories/", json={}, headers=auth_headers).status_code == 422


# --- GET /api/v1/stories/{story_id} ---

def test_get_story_by_id_returns_story(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    story = Story(child_id=test_child.id, theme="ocean", title="Ocean Tale")
    db.add(story)
    db.commit()
    db.refresh(story)

    response = client.get(f"/api/v1/stories/{story.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(story.id)
    assert data["title"] == "Ocean Tale"
    assert "status" not in data


def test_get_story_by_id_not_found_returns_404(client: TestClient, auth_headers: dict) -> None:
    assert client.get(f"/api/v1/stories/{uuid.uuid4()}", headers=auth_headers).status_code == 404


def test_get_story_by_id_unauthenticated_returns_401(
    client: TestClient, db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="theme")
    db.add(story)
    db.commit()
    db.refresh(story)

    assert client.get(f"/api/v1/stories/{story.id}").status_code == 401


# --- GET /api/v1/stories/in_progress ---

def test_get_in_progress_returns_draft_id_and_status(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="volcano")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    response = client.get("/api/v1/stories/in_progress", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["draft_id"] == str(draft.id)
    assert data["status"] == DraftStatus.GENERATING_ABSTRACT


def test_get_in_progress_returns_404_when_none(
    client: TestClient, auth_headers: dict
) -> None:
    assert client.get("/api/v1/stories/in_progress", headers=auth_headers).status_code == 404


def test_get_in_progress_returns_404_when_no_draft(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    db.add(Story(child_id=test_child.id, theme="ocean"))
    db.commit()

    assert client.get("/api/v1/stories/in_progress", headers=auth_headers).status_code == 404


def test_get_in_progress_unauthenticated_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/stories/in_progress").status_code == 401


# --- GET /api/v1/stories/{draft_id}/abstracts ---

def test_get_abstracts_returns_list_when_ready(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    abstracts = ["Abstract A", "Abstract B", "Abstract C"]
    draft = StoryDraft(child_id=test_child.id, theme="jungle", abstracts=abstracts)
    db.add(draft)
    db.commit()
    db.refresh(draft)

    response = client.get(f"/api/v1/stories/{draft.id}/abstracts", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == abstracts


def test_get_abstracts_returns_202_while_generating(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="jungle")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    assert client.get(f"/api/v1/stories/{draft.id}/abstracts", headers=auth_headers).status_code == 202


def test_get_abstracts_returns_404_for_unknown_draft(
    client: TestClient, auth_headers: dict
) -> None:
    assert client.get(f"/api/v1/stories/{uuid.uuid4()}/abstracts", headers=auth_headers).status_code == 404


# --- POST /api/v1/stories/{draft_id}/select_abstract ---

def test_select_abstract_returns_updated_status(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="jungle",
        abstracts=["Abstract A", "Abstract B"],
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    response = client.post(
        f"/api/v1/stories/{draft.id}/select_abstract",
        json={"abstract": "A brave explorer in the jungle."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["draft_id"] == str(draft.id)
    assert data["status"] == DraftStatus.GENERATING_TEXT


def test_select_abstract_returns_409_when_abstracts_not_ready(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="jungle")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    response = client.post(
        f"/api/v1/stories/{draft.id}/select_abstract",
        json={"abstract": "Some abstract"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_select_abstract_returns_404_for_unknown_draft(
    client: TestClient, auth_headers: dict
) -> None:
    response = client.post(
        f"/api/v1/stories/{uuid.uuid4()}/select_abstract",
        json={"abstract": "Some abstract"},
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- POST /api/v1/stories/{draft_id}/generate_story ---

def test_generate_story_accepted_when_abstract_selected(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="forest",
        abstracts=["Abstract A"],
        selected_abstract="Abstract A",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    with patch("app.api.v1.stories.generate_story_and_audio_background"):
        response = client.post(f"/api/v1/stories/{draft.id}/generate_story", headers=auth_headers)
    assert response.status_code == 202
    data = response.json()
    assert data["draft_id"] == str(draft.id)
    assert data["status"] == DraftStatus.GENERATING_TEXT


def test_generate_story_triggers_background_task(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="forest",
        abstracts=["Abstract A"],
        selected_abstract="Abstract A",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    with patch("app.api.v1.stories.generate_story_and_audio_background") as mock_bg:
        client.post(f"/api/v1/stories/{draft.id}/generate_story", headers=auth_headers)
    mock_bg.assert_called_once_with(draft.id)


def test_generate_story_returns_409_when_no_abstract_selected(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="ocean")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    assert client.post(f"/api/v1/stories/{draft.id}/generate_story", headers=auth_headers).status_code == 409


def test_generate_story_returns_404_when_not_found(client: TestClient, auth_headers: dict) -> None:
    assert client.post(f"/api/v1/stories/{uuid.uuid4()}/generate_story", headers=auth_headers).status_code == 404


def test_generate_story_unauthenticated_returns_401(
    client: TestClient, db: Session, test_child: Child
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="theme")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    assert client.post(f"/api/v1/stories/{draft.id}/generate_story").status_code == 401


# --- DELETE /api/v1/stories/{story_id} ---

def test_delete_story_returns_204(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    story = Story(child_id=test_child.id, theme="ocean")
    db.add(story)
    db.commit()
    db.refresh(story)

    assert client.delete(f"/api/v1/stories/{story.id}", headers=auth_headers).status_code == 204


def test_delete_story_hides_story_from_api(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    story = Story(child_id=test_child.id, theme="forest")
    db.add(story)
    db.commit()
    db.refresh(story)

    client.delete(f"/api/v1/stories/{story.id}", headers=auth_headers)

    assert client.get(f"/api/v1/stories/{story.id}", headers=auth_headers).status_code == 404
    db.refresh(story)
    assert story.is_deleted is True


def test_delete_story_excluded_from_list(
    client: TestClient, db: Session, test_child: Child, auth_headers: dict
) -> None:
    story = Story(child_id=test_child.id, theme="forest")
    db.add(story)
    db.commit()
    db.refresh(story)

    client.delete(f"/api/v1/stories/{story.id}", headers=auth_headers)

    assert client.get("/api/v1/stories/", headers=auth_headers).json()["total"] == 0


def test_delete_story_returns_404_for_unknown_id(client: TestClient, auth_headers: dict) -> None:
    assert client.delete(f"/api/v1/stories/{uuid.uuid4()}", headers=auth_headers).status_code == 404


def test_delete_story_unauthenticated_returns_401(
    client: TestClient, db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="theme")
    db.add(story)
    db.commit()
    db.refresh(story)

    assert client.delete(f"/api/v1/stories/{story.id}").status_code == 401
