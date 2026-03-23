"""Tests for app/crud/story.py — story creation and retrieval."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.story import (
    create_story,
    delete_story,
    get_draft_by_id,
    get_in_progress_story_by_user_id,
    get_stories_by_user_id,
    get_story_by_id,
    mark_story_abstract_ready,
    select_abstract,
    update_story_audio,
    update_story_content,
)
from app.models.child import Child
from app.models.story import Story
from app.models.story_draft import StoryDraft, DraftStatus, get_draft_status
from app.models.user import User
from app.schemas.story import StoryCreate


# --- create_story ---

def test_create_story_creates_draft_only(db: Session, test_child: Child) -> None:
    story_in = StoryCreate(child_id=test_child.id, theme="space adventure")
    result = create_story(db, story_in)

    assert result.draft_id is not None
    assert result.status == DraftStatus.GENERATING_ABSTRACT

    # No Story record should exist yet
    stories = db.scalars(select(Story).where(Story.child_id == test_child.id)).all()
    assert len(stories) == 0

    draft = db.get(StoryDraft, result.draft_id)
    assert draft is not None
    assert draft.theme == "space adventure"


# --- mark_story_abstract_ready ---

def test_mark_story_abstract_ready_persists_on_draft(
    db: Session, test_child: Child
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="jungle")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    abstracts = ["Abstract A", "Abstract B", "Abstract C"]
    mark_story_abstract_ready(db, draft.id, abstracts)

    db.refresh(draft)
    assert draft.abstracts == abstracts
    assert get_draft_status(draft) == DraftStatus.ABSTRACT_READY


def test_mark_story_abstract_ready_noop_for_unknown_id(db: Session) -> None:
    mark_story_abstract_ready(db, uuid.uuid4(), ["some abstract"])


# --- select_abstract ---

def test_select_abstract_persists_on_draft(
    db: Session, test_child: Child
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="jungle",
        abstracts=["Abstract A", "Abstract B"],
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    select_abstract(db, draft.id, "A brave explorer in the jungle.")

    db.refresh(draft)
    assert draft.selected_abstract == "A brave explorer in the jungle."
    assert get_draft_status(draft) == DraftStatus.GENERATING_TEXT


def test_select_abstract_noop_for_unknown_id(db: Session) -> None:
    select_abstract(db, uuid.uuid4(), "some abstract")


# --- update_story_content ---

def test_update_story_content_sets_fields_and_advances_draft(
    db: Session, test_child: Child
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="space",
        abstracts=["Abstract A"],
        selected_abstract="Abstract A",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    update_story_content(db, draft.id, "Space Quest", "A long time ago in a galaxy...")

    db.refresh(draft)
    assert draft.title == "Space Quest"
    assert draft.generated_text == "A long time ago in a galaxy..."
    assert get_draft_status(draft) == DraftStatus.GENERATING_AUDIO


def test_update_story_content_noop_for_unknown_id(db: Session) -> None:
    update_story_content(db, uuid.uuid4(), "title", "content")


# --- update_story_audio ---

def test_update_story_audio_creates_story_and_deletes_draft(
    db: Session, test_child: Child
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="ocean",
        abstracts=["Abstract A", "Abstract B"],
        selected_abstract="Abstract A",
        generated_text="The ocean is deep...",
        title="Ocean Quest",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    draft_id = draft.id

    story = update_story_audio(db, draft_id, "https://audio.example.com/story.mp3")

    assert story is not None
    assert story.child_id == test_child.id
    assert story.theme == "ocean"
    assert story.title == "Ocean Quest"
    assert story.abstracts == ["Abstract A", "Abstract B"]
    assert story.abstract == "Abstract A"
    assert story.content == "The ocean is deep..."
    assert story.audio_url == "https://audio.example.com/story.mp3"
    assert db.get(StoryDraft, draft_id) is None


def test_update_story_audio_noop_for_unknown_id(db: Session) -> None:
    assert update_story_audio(db, uuid.uuid4(), "https://audio.example.com/story.mp3") is None


# --- get_draft_by_id ---

def test_get_draft_by_id_returns_draft(
    db: Session, test_user: User, test_child: Child
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="forest")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    result = get_draft_by_id(db, draft.id, test_user.id)
    assert result is not None
    assert result.id == draft.id


def test_get_draft_by_id_wrong_user_returns_none(db: Session, test_child: Child) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="forest")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    assert get_draft_by_id(db, draft.id, uuid.uuid4()) is None


def test_get_draft_by_id_unknown_returns_none(db: Session, test_user: User) -> None:
    assert get_draft_by_id(db, uuid.uuid4(), test_user.id) is None


# --- get_stories_by_user_id ---

def test_get_stories_returns_user_stories(
    db: Session, test_user: User, test_child: Child
) -> None:
    db.add(Story(child_id=test_child.id, theme="forest"))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=20, offset=0)
    assert result.total == 1
    assert result.items[0].theme == "forest"


def test_get_stories_pagination_limits_results(
    db: Session, test_user: User, test_child: Child
) -> None:
    for i in range(5):
        db.add(Story(child_id=test_child.id, theme=f"theme{i}"))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=2, offset=0)
    assert result.total == 5
    assert len(result.items) == 2


def test_get_stories_offset_skips_rows(
    db: Session, test_user: User, test_child: Child
) -> None:
    for i in range(3):
        db.add(Story(child_id=test_child.id, theme=f"theme{i}"))
    db.commit()

    result = get_stories_by_user_id(db, test_user.id, limit=10, offset=2)
    assert result.total == 3
    assert len(result.items) == 1


def test_get_stories_empty_for_unknown_user(db: Session, test_child: Child) -> None:
    db.add(Story(child_id=test_child.id, theme="theme"))
    db.commit()

    result = get_stories_by_user_id(db, uuid.uuid4(), limit=20, offset=0)
    assert result.total == 0
    assert result.items == []


# --- get_in_progress_story_by_user_id ---

def test_get_in_progress_story_returns_draft_id_and_status(
    db: Session, test_user: User, test_child: Child
) -> None:
    draft = StoryDraft(child_id=test_child.id, theme="jungle")
    db.add(draft)
    db.commit()
    db.refresh(draft)

    result = get_in_progress_story_by_user_id(db, test_user.id)
    assert result is not None
    assert result.draft_id == draft.id
    assert result.status == DraftStatus.GENERATING_ABSTRACT


def test_get_in_progress_story_returns_none_when_no_draft(
    db: Session, test_user: User, test_child: Child
) -> None:
    # Completed story — no draft
    db.add(Story(child_id=test_child.id, theme="ocean"))
    db.commit()

    assert get_in_progress_story_by_user_id(db, test_user.id) is None


def test_get_in_progress_story_returns_none_when_no_stories(
    db: Session, test_user: User
) -> None:
    assert get_in_progress_story_by_user_id(db, test_user.id) is None


def test_get_in_progress_story_returns_none_for_unknown_user(
    db: Session, test_child: Child
) -> None:
    db.add(StoryDraft(child_id=test_child.id, theme="forest"))
    db.commit()

    assert get_in_progress_story_by_user_id(db, uuid.uuid4()) is None


def test_get_in_progress_story_reflects_draft_state(
    db: Session, test_user: User, test_child: Child
) -> None:
    draft = StoryDraft(
        child_id=test_child.id, theme="jungle",
        abstracts=["A", "B"],
        selected_abstract="A",
    )
    db.add(draft)
    db.commit()

    result = get_in_progress_story_by_user_id(db, test_user.id)
    assert result is not None
    assert result.status == DraftStatus.GENERATING_TEXT


# --- get_story_by_id ---

def test_get_story_by_id_returns_story(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="underwater")
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
    story = Story(child_id=test_child.id, theme="theme")
    db.add(story)
    db.commit()
    db.refresh(story)

    assert get_story_by_id(db, story.id, uuid.uuid4()) is None


# --- delete_story ---

def test_delete_story_soft_deletes_and_returns_true(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="jungle")
    db.add(story)
    db.commit()
    db.refresh(story)

    result = delete_story(db, story.id, test_user.id)
    assert result is True
    db.refresh(story)
    assert story.is_deleted is True
    assert db.get(Story, story.id) is not None


def test_delete_story_hides_from_queries(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="jungle")
    db.add(story)
    db.commit()
    db.refresh(story)

    delete_story(db, story.id, test_user.id)

    assert get_story_by_id(db, story.id, test_user.id) is None
    assert get_stories_by_user_id(db, test_user.id, limit=20, offset=0).total == 0


def test_delete_story_returns_false_for_unknown_id(db: Session, test_user: User) -> None:
    assert delete_story(db, uuid.uuid4(), test_user.id) is False


def test_delete_story_returns_false_for_wrong_user(db: Session, test_child: Child) -> None:
    story = Story(child_id=test_child.id, theme="theme")
    db.add(story)
    db.commit()
    db.refresh(story)

    assert delete_story(db, story.id, uuid.uuid4()) is False
    db.refresh(story)
    assert story.is_deleted is False


def test_delete_story_returns_false_when_already_deleted(
    db: Session, test_user: User, test_child: Child
) -> None:
    story = Story(child_id=test_child.id, theme="forest", is_deleted=True)
    db.add(story)
    db.commit()
    db.refresh(story)

    assert delete_story(db, story.id, test_user.id) is False
