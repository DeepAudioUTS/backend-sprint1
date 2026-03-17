"""Tests for app/crud/story.py — story creation and retrieval."""

import uuid

from sqlalchemy.orm import Session

from app.crud.story import (
    create_story,
    get_cached_abstracts,
    get_in_progress_story_by_user_id,
    get_stories_by_user_id,
    get_story_by_id,
    mark_story_abstract_ready,
    select_abstract,
    update_story_audio,
    update_story_content,
)
from app.models.child import Child
from app.models.story import Story, StoryStatus
from app.models.user import User
from app.schemas.story import StoryCreate


# --- create_story ---

def test_create_story_sets_generating_abstract_status(db: Session, test_child: Child) -> None:
    story_in = StoryCreate(child_id=test_child.id, theme="space adventure")
    result = create_story(db, story_in)

    assert result.child_id == test_child.id
    assert result.theme == "space adventure"
    assert result.status == StoryStatus.GENERATING_ABSTRACT
    assert result.title is None
    assert result.abstract is None
    assert result.content is None
    assert result.audio_url is None


def test_create_story_assigns_uuid(db: Session, test_child: Child) -> None:
    story_in = StoryCreate(child_id=test_child.id, theme="ocean")
    result = create_story(db, story_in)
    assert result.id is not None


# --- mark_story_abstract_ready ---

def test_mark_story_abstract_ready_caches_abstracts_and_advances_status(
    db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="jungle", status=StoryStatus.GENERATING_ABSTRACT)
    db.add(story)
    db.commit()
    db.refresh(story)

    abstracts = ["Abstract A", "Abstract B", "Abstract C"]
    mark_story_abstract_ready(db, story.id, abstracts)

    db.refresh(story)
    assert story.abstract is None
    assert story.status == StoryStatus.ABSTRACT_READY
    assert get_cached_abstracts(story.id) == abstracts


def test_mark_story_abstract_ready_noop_for_unknown_id(db: Session) -> None:
    # Should not raise
    mark_story_abstract_ready(db, uuid.uuid4(), ["some abstract"])


# --- select_abstract ---

def test_select_abstract_persists_abstract_and_advances_status(
    db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="jungle", status=StoryStatus.ABSTRACT_READY)
    db.add(story)
    db.commit()
    db.refresh(story)

    select_abstract(db, story.id, "A brave explorer in the jungle.")

    db.refresh(story)
    assert story.abstract == "A brave explorer in the jungle."
    assert story.status == StoryStatus.GENERATING_TEXT


def test_select_abstract_noop_for_unknown_id(db: Session) -> None:
    # Should not raise
    select_abstract(db, uuid.uuid4(), "some abstract")


# --- update_story_content ---

def test_update_story_content_sets_title_content_and_advances_status(
    db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="space", status=StoryStatus.GENERATING_TEXT)
    db.add(story)
    db.commit()
    db.refresh(story)

    update_story_content(db, story.id, "Space Quest", "A long time ago in a galaxy...")

    db.refresh(story)
    assert story.title == "Space Quest"
    assert story.content == "A long time ago in a galaxy..."
    assert story.status == StoryStatus.GENERATING_AUDIO


def test_update_story_content_noop_for_unknown_id(db: Session) -> None:
    update_story_content(db, uuid.uuid4(), "title", "content")


# --- update_story_audio ---

def test_update_story_audio_sets_audio_url_and_completes(
    db: Session, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="ocean", status=StoryStatus.GENERATING_AUDIO)
    db.add(story)
    db.commit()
    db.refresh(story)

    update_story_audio(db, story.id, "https://audio.example.com/story.mp3")

    db.refresh(story)
    assert story.audio_url == "https://audio.example.com/story.mp3"
    assert story.status == StoryStatus.COMPLETED


def test_update_story_audio_noop_for_unknown_id(db: Session) -> None:
    update_story_audio(db, uuid.uuid4(), "https://audio.example.com/story.mp3")


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


# --- get_in_progress_story_by_user_id ---

def test_get_in_progress_story_returns_in_progress_story(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="jungle", status=StoryStatus.GENERATING_ABSTRACT)
    db.add(story)
    db.commit()
    db.refresh(story)

    result = get_in_progress_story_by_user_id(db, test_user.id)
    assert result is not None
    assert result.story_id == story.id
    assert result.status == StoryStatus.GENERATING_ABSTRACT


def test_get_in_progress_story_returns_none_when_all_completed(
    db: Session, test_user: User, test_child: Child
) -> None:
    db.add(Story(child_id=test_child.id, theme="ocean", status=StoryStatus.COMPLETED))
    db.commit()

    assert get_in_progress_story_by_user_id(db, test_user.id) is None


def test_get_in_progress_story_returns_none_when_no_stories(
    db: Session, test_user: User
) -> None:
    assert get_in_progress_story_by_user_id(db, test_user.id) is None


def test_get_in_progress_story_returns_none_for_unknown_user(
    db: Session, test_child: Child
) -> None:
    db.add(Story(child_id=test_child.id, theme="forest", status=StoryStatus.GENERATING_TEXT))
    db.commit()

    assert get_in_progress_story_by_user_id(db, uuid.uuid4()) is None


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
