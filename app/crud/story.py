import uuid

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.child import Child
from app.models.story import Story
from app.models.story_draft import StoryDraft, DraftStatus, get_draft_status
from app.schemas.story import StoryCreate, StoryResponse, StoryListResponse, InProgressStoryResponse, AbstractCandidate


# ---------------------------------------------------------------------------
# DB helper functions
# ---------------------------------------------------------------------------

def get_draft_by_id(
    db: Session, draft_id: uuid.UUID, user_id: uuid.UUID
) -> StoryDraft | None:
    """Return a StoryDraft with ownership check."""
    return db.scalars(
        select(StoryDraft)
        .join(Child, StoryDraft.child_id == Child.id)
        .where(StoryDraft.id == draft_id, Child.user_id == user_id)
    ).first()


def create_story(db: Session, story_in: StoryCreate) -> InProgressStoryResponse:
    """Create a StoryDraft to begin the story generation pipeline.

    The Story record is not created here — it is created only when audio
    generation completes (see update_story_audio).

    Args:
        db: Database session.
        story_in: Story creation request (child_id, theme).

    Returns:
        InProgressStoryResponse with draft_id and initial status.
    """
    draft = StoryDraft(
        child_id=story_in.child_id,
        theme=story_in.theme,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return InProgressStoryResponse(draft_id=draft.id, status=DraftStatus.GENERATING_ABSTRACT)


def mark_story_abstract_ready(
    db: Session, draft_id: uuid.UUID, abstracts: list[str], story_prompts: list[str]
) -> None:
    """Store generated abstract candidates and their story prompts on the draft.

    Draft state transition: GENERATING_ABSTRACT → ABSTRACT_READY

    Args:
        db: Database session.
        draft_id: Target draft ID.
        abstracts: List of generated abstract candidates.
        story_prompts: List of story prompts corresponding to each abstract.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.abstracts = abstracts
    draft.story_prompts = story_prompts
    db.commit()


def select_abstract(db: Session, draft_id: uuid.UUID, abstract: str, story_prompt: str) -> None:
    """Persist the user-selected abstract and its story prompt on the draft.

    Draft state transition: ABSTRACT_READY → GENERATING_TEXT

    Args:
        db: Database session.
        draft_id: Target draft ID.
        abstract: The abstract chosen by the user.
        story_prompt: The story prompt paired with the selected abstract.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.selected_abstract = abstract
    draft.selected_story_prompt = story_prompt
    db.commit()


def mark_story_failed(db: Session, draft_id: uuid.UUID, error: str) -> None:
    """Record a failure on the draft so the client can see what went wrong.

    The failed step is inferred by get_draft_status() from existing field state,
    so no explicit step parameter is needed here.

    Args:
        db: Database session.
        draft_id: Target draft ID.
        error: Human-readable error message.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.error = error
    db.commit()


def clear_draft_error(db: Session, draft_id: uuid.UUID) -> None:
    """Clear the error field so the draft can be retried.

    Args:
        db: Database session.
        draft_id: Target draft ID.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.error = None
    db.commit()


def update_story_content(
    db: Session, draft_id: uuid.UUID, title: str, content: str
) -> None:
    """Update the draft's title and generated text.

    Draft state transition: GENERATING_TEXT → GENERATING_AUDIO

    Args:
        db: Database session.
        draft_id: Target draft ID.
        title: Generated story title.
        content: Generated story body text.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    draft.title = title
    draft.generated_text = content
    db.commit()


def update_story_audio(
    db: Session, draft_id: uuid.UUID, audio_url: str
) -> Story | None:
    """Create the final Story record from the draft, then delete the draft.

    This is the only place where a Story is created. All data accumulated
    in the draft is copied to the new Story record.

    Args:
        db: Database session.
        draft_id: Target draft ID.
        audio_url: URL of the generated audio file.

    Returns:
        The newly created Story, or None if the draft was not found.
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


def get_stories_by_user_id(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> StoryListResponse:
    """Retrieve a paginated list of stories associated with a user ID.

    Returns all non-deleted stories owned by the user via their children.

    Args:
        db: Database session.
        user_id: Parent user's ID.
        limit: Maximum number of results to return.
        offset: Starting position for retrieval.

    Returns:
        Response object containing the story list and count metadata.
    """
    base_stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    )

    total: int = db.scalar(
        select(func.count()).select_from(base_stmt.subquery())
    ) or 0

    stories = db.scalars(
        base_stmt.order_by(Story.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return StoryListResponse(
        items=[StoryResponse.model_validate(s) for s in stories],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_in_progress_story_by_user_id(
    db: Session, user_id: uuid.UUID
) -> InProgressStoryResponse | None:
    """Retrieve the single in-progress story for a user via their active StoryDraft.

    Args:
        db: Database session.
        user_id: Parent user's ID.

    Returns:
        InProgressStoryResponse with draft_id and inferred status, or None.
    """
    draft = db.scalars(
        select(StoryDraft)
        .join(Child, StoryDraft.child_id == Child.id)
        .where(Child.user_id == user_id)
    ).first()
    if draft is None:
        return None
    return InProgressStoryResponse(draft_id=draft.id, status=get_draft_status(draft))


def delete_story(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Soft-delete a story by ID (with ownership check).

    Sets is_deleted=True so the record is retained for data analysis
    but hidden from all user-facing queries.

    Args:
        db: Database session.
        story_id: ID of the story to delete.
        user_id: ID of the requesting user.

    Returns:
        True if hidden, False if not found or unauthorized.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    )
    story = db.scalars(stmt).first()
    if story is None:
        return False
    story.is_deleted = True
    db.commit()
    return True


def get_story_audio_url(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return the audio_url for a story (with ownership check)."""
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return story.audio_url


def fetch_audio_bytes(audio_url: str) -> tuple[bytes, str]:
    """Fetch audio data from the TTS service."""
    url = f"{settings.TTS_API_URL}{audio_url}"
    response = httpx.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "audio/mpeg")
    return response.content, content_type


def get_story_by_id(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> StoryResponse | None:
    """Retrieve a single story by ID (with ownership check)."""
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id, Story.is_deleted == False)  # noqa: E712
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return StoryResponse.model_validate(story)


# ---------------------------------------------------------------------------
# External API stub functions (replace with real implementations)
# ---------------------------------------------------------------------------

def _call_abstract_api(theme: str) -> list[AbstractCandidate]:
    """Call the abstract generation API.

    Returns a list of abstract candidates, each with an abstract and a story_prompt.
    """
    url = f"{settings.LLM_API_URL}/api/v1/abstract/generate"
    print(url)
    response = httpx.post(url, json={"theme": theme})
    response.raise_for_status()
    return [AbstractCandidate(**item) for item in response.json()]


def _call_story_api(abstract: str, story_prompt: str) -> tuple[str, str]:
    """Call the story generation API."""
    url = f"{settings.LLM_API_URL}/api/v1/story/generate"
    response = httpx.post(url, json={"abstract": abstract, "story_prompt": story_prompt})
    response.raise_for_status()
    data = response.json()
    return data["title"], data["content"]


def _call_audio_api(title: str, content: str) -> str:
    """Call the audio generation API."""
    url = f"{settings.TTS_API_URL}/audio/generate"
    response = httpx.post(url, json={"text": content, "title": title})
    response.raise_for_status()
    return response.json()["audio_url"]


# ---------------------------------------------------------------------------
# Background task workers
# ---------------------------------------------------------------------------

def generate_abstract_background(draft_id: uuid.UUID, theme: str) -> None:
    """Background task: generate abstract candidates and store them on the draft.

    Draft state transition: GENERATING_ABSTRACT → ABSTRACT_READY (or FAILED_GENERATING_ABSTRACT on error)

    Args:
        draft_id: ID of the StoryDraft to update.
        theme: Story theme passed to the abstract API.
    """
    db = SessionLocal()
    print("background")
    try:
        candidates = _call_abstract_api(theme)
        abstracts = [c.abstract for c in candidates]
        story_prompts = [c.story_prompt for c in candidates]
        mark_story_abstract_ready(db, draft_id, abstracts, story_prompts)
    except Exception as e:
        mark_story_failed(db, draft_id, str(e))
    finally:
        db.close()


def generate_story_and_audio_background(draft_id: uuid.UUID) -> None:
    """Background task: generate story text, then audio, then create the Story record.

    Draft state transitions:
        GENERATING_TEXT → (story API) → GENERATING_AUDIO → (audio API) → Story created, draft deleted
        On story API error  → FAILED_GENERATING_TEXT
        On audio API error  → FAILED_GENERATING_AUDIO

    Args:
        draft_id: ID of the StoryDraft to process.
    """
    db = SessionLocal()
    try:
        draft = db.get(StoryDraft, draft_id)
        if draft is None:
            return

        # Step 1: generate story text
        try:
            title, content = _call_story_api(draft.selected_abstract or "", draft.selected_story_prompt or "")
        except Exception as e:
            mark_story_failed(db, draft_id, str(e))
            return
        update_story_content(db, draft_id, title, content)

        # Step 2: generate audio, then create Story and delete draft
        try:
            audio_url = _call_audio_api(title, content)
        except Exception as e:
            mark_story_failed(db, draft_id, str(e))
            return
        update_story_audio(db, draft_id, audio_url)
    finally:
        db.close()


def generate_audio_background(draft_id: uuid.UUID) -> None:
    """Background task: generate audio only (used when retrying FAILED_GENERATING_AUDIO).

    Reads the already-generated title and text from the draft.

    Draft state transition: GENERATING_AUDIO → Story created, draft deleted (or FAILED_GENERATING_AUDIO on error)

    Args:
        draft_id: ID of the StoryDraft to process.
    """
    db = SessionLocal()
    try:
        draft = db.get(StoryDraft, draft_id)
        if draft is None:
            return
        try:
            audio_url = _call_audio_api(draft.title or "", draft.generated_text or "")
        except Exception as e:
            mark_story_failed(db, draft_id, str(e))
            return
        update_story_audio(db, draft_id, audio_url)
    finally:
        db.close()
