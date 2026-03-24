import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.child import Child
from app.models.story import Story
from app.models.story_draft import StoryDraft


def get_draft(db: Session, draft_id: uuid.UUID) -> StoryDraft | None:
    """Return a StoryDraft by primary key (no ownership check)."""
    return db.get(StoryDraft, draft_id)


def get_draft_by_id(
    db: Session, draft_id: uuid.UUID, user_id: uuid.UUID
) -> StoryDraft | None:
    """Return a StoryDraft with ownership check."""
    return db.scalars(
        select(StoryDraft)
        .join(Child, StoryDraft.child_id == Child.id)
        .where(StoryDraft.id == draft_id, Child.user_id == user_id)
    ).first()


def create_draft(db: Session, child_id: uuid.UUID, theme: str) -> StoryDraft:
    """Insert a new StoryDraft and return it."""
    draft = StoryDraft(child_id=child_id, theme=theme)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def mark_abstract_ready(
    db: Session, draft_id: uuid.UUID, abstracts: list[str], story_prompts: list[str]
) -> None:
    """Store generated abstract candidates and their paired story prompts."""
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.abstracts = abstracts
    draft.story_prompts = story_prompts
    db.commit()


def set_selected_abstract(
    db: Session, draft_id: uuid.UUID, abstract: str, story_prompt: str
) -> None:
    """Persist the user-selected abstract and its paired story prompt."""
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.selected_abstract = abstract
    draft.selected_story_prompt = story_prompt
    db.commit()


def mark_failed(db: Session, draft_id: uuid.UUID, error: str) -> None:
    """Record a failure message on the draft."""
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.error = error
    db.commit()
    draft = db.get(StoryDraft, draft_id)
    print(draft.error)

def clear_error(db: Session, draft_id: uuid.UUID) -> None:
    """Clear the error field so the draft can be retried."""
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.error = None
    db.commit()


def set_story_content(
    db: Session, draft_id: uuid.UUID, title: str, content: str
) -> None:
    """Update the draft's title and generated text."""
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.title = title
    draft.generated_text = content
    db.commit()


def finalize_story(db: Session, draft_id: uuid.UUID, audio_url: str) -> Story | None:
    """Create the final Story record from the draft, then delete the draft.

    Returns the newly created Story, or None if the draft was not found.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return None
    story = Story(
        child_id=draft.child_id,
        theme=draft.theme,
        title=draft.title,
        abstracts=draft.abstracts,
        story_prompts=draft.story_prompts,
        abstract=draft.selected_abstract,
        story_prompt=draft.selected_story_prompt,
        content=draft.generated_text,
        audio_url=audio_url,
    )
    db.add(story)
    db.delete(draft)
    db.commit()
    db.refresh(story)
    return story


def get_stories(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Story], int]:
    """Return a paginated list of non-deleted stories for a user, plus total count."""
    base_stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    )
    total: int = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    stories = db.scalars(
        base_stmt.order_by(Story.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(stories), total


def get_active_draft_by_user(db: Session, user_id: uuid.UUID) -> StoryDraft | None:
    """Return the single active StoryDraft for a user, or None."""
    return db.scalars(
        select(StoryDraft)
        .join(Child, StoryDraft.child_id == Child.id)
        .where(Child.user_id == user_id)
    ).first()


def soft_delete_story(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Set is_deleted=True on a story (with ownership check).

    Returns True if the story was found and deleted, False otherwise.
    """
    story = db.scalars(
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    ).first()
    if story is None:
        return False
    story.is_deleted = True
    db.commit()
    return True


def get_story_audio_url(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return the audio_url for a story (with ownership check)."""
    story = db.scalars(
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    ).first()
    return story.audio_url if story else None


def get_story_by_id(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> Story | None:
    """Return a single Story by ID (with ownership check)."""
    return db.scalars(
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    ).first()
