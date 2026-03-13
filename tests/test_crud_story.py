"""Tests for app/crud/story.py — story creation and retrieval."""

import uuid

from sqlalchemy.orm import Session

from app.crud.story import create_story, get_stories_by_user_id, get_story_by_id
from app.models.child import Child
from app.models.story import Story, StoryStatus
from app.models.user import User
from app.schemas.story import StoryCreate


# --- create_story ---

def test_create_story_sets_generating_text_status(db: Session, test_child: Child) -> None:
    story_in = StoryCreate(child_id=test_child.id, theme="space adventure")
    result = create_story(db, story_in)

    assert result.child_id == test_child.id
    assert result.theme == "space adventure"
    assert result.status == StoryStatus.GENERATING_TEXT
    assert result.title is None
    assert result.content is None
    assert result.audio_url is None


def test_create_story_assigns_uuid(db: Session, test_child: Child) -> None:
    story_in = StoryCreate(child_id=test_child.id, theme="ocean")
    result = create_story(db, story_in)
    assert result.id is not None


# --- get_stories_by_user_id ---

def test_get_stories_returns_user_stories(
    db: Session, test_user: User, test_child: Child
) -> None:
    db.add(Story(child_id=test_child.id, theme="forest", status=StoryStatus.COMPLETED))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=20, offset=0)
    assert result.total == 1
    assert result.items[0].theme == "forest"


def test_get_stories_pagination_limits_results(
    db: Session, test_user: User, test_child: Child
) -> None:
    for i in range(5):
        db.add(Story(child_id=test_child.id, theme=f"theme{i}", status=StoryStatus.GENERATING_TEXT))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=2, offset=0)
    assert result.total == 5
    assert len(result.items) == 2
    assert result.limit == 2
    assert result.offset == 0


def test_get_stories_offset_skips_rows(
    db: Session, test_user: User, test_child: Child
) -> None:
    for i in range(3):
        db.add(Story(child_id=test_child.id, theme=f"theme{i}", status=StoryStatus.GENERATING_TEXT))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=10, offset=2)
    assert result.total == 3
    assert len(result.items) == 1


def test_get_stories_empty_for_unknown_user(db: Session, test_child: Child) -> None:
    db.add(Story(child_id=test_child.id, theme="theme", status=StoryStatus.GENERATING_TEXT))
    db.commit()

    result = get_stories_by_user_id(db, uuid.uuid4(), limit=20, offset=0)
    assert result.total == 0
    assert result.items == []


# --- get_story_by_id ---

def test_get_story_by_id_returns_story(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="underwater", status=StoryStatus.COMPLETED)
    db.add(story)
    db.commit()
    db.refresh(story)

    result = get_story_by_id(db, story.id, test_user.id)
    assert result is not None
    assert result.id == story.id
    assert result.theme == "underwater"


def test_get_story_by_id_not_found_returns_none(db: Session, test_user: User) -> None:
    assert get_story_by_id(db, uuid.uuid4(), test_user.id) is None


def test_get_story_by_id_wrong_user_returns_none(db: Session, test_child: Child) -> None:
    story = Story(child_id=test_child.id, theme="theme", status=StoryStatus.GENERATING_TEXT)
    db.add(story)
    db.commit()
    db.refresh(story)

    assert get_story_by_id(db, story.id, uuid.uuid4()) is None
