import uuid
import time

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.child import Child
from app.models.story import Story, StoryStatus
from app.schemas.story import StoryCreate, StoryResponse, StoryListResponse, InProgressStoryResponse


# ---------------------------------------------------------------------------
# DB helper functions
# ---------------------------------------------------------------------------

def create_story(db: Session, story_in: StoryCreate) -> StoryResponse:
    """Create a new story record with status generating_abstract.

    Args:
        db: Database session.
        story_in: Story creation request (child_id, theme).

    Returns:
        Response object of the created story.
    """
    story = Story(
        child_id=story_in.child_id,
        theme=story_in.theme,
        status=StoryStatus.GENERATING_ABSTRACT,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return StoryResponse.model_validate(story)


_abstracts_cache: dict[uuid.UUID, list[str]] = {}


def mark_story_abstract_ready(
    db: Session, story_id: uuid.UUID, abstracts: list[str]
) -> None:
    """Store generated abstracts in cache and advance status to abstract_ready.

    Abstracts are intentionally not persisted to the DB — they are held in
    memory until the user selects one via select_abstract().

    Args:
        db: Database session.
        story_id: Target story ID.
        abstracts: List of generated abstract candidates.
    """
    _abstracts_cache[story_id] = abstracts
    story = db.get(Story, story_id)
    if story is None:
        return
    story.status = StoryStatus.ABSTRACT_READY
    db.commit()


def get_cached_abstracts(story_id: uuid.UUID) -> list[str] | None:
    """Return cached abstract candidates for a story.

    Args:
        story_id: Target story ID.

    Returns:
        List of abstract candidates, or None if not yet cached.
    """
    return _abstracts_cache.get(story_id)


def select_abstract(db: Session, story_id: uuid.UUID, abstract: str) -> None:
    """Persist the user-selected abstract and advance status to generating_text.

    Args:
        db: Database session.
        story_id: Target story ID.
        abstract: The abstract chosen by the user.
    """
    story = db.get(Story, story_id)
    if story is None:
        return
    story.abstract = abstract
    story.status = StoryStatus.GENERATING_TEXT
    db.commit()


def update_story_content(
    db: Session, story_id: uuid.UUID, title: str, content: str
) -> None:
    """Update the story's title and content, advance status to generating_audio.

    Args:
        db: Database session.
        story_id: Target story ID.
        title: Generated story title.
        content: Generated story body text.
    """
    story = db.get(Story, story_id)
    if story is None:
        return
    story.title = title
    story.content = content
    story.status = StoryStatus.GENERATING_AUDIO
    db.commit()


def update_story_audio(
    db: Session, story_id: uuid.UUID, audio_url: str
) -> None:
    """Update the story's audio URL and set status to completed.

    Args:
        db: Database session.
        story_id: Target story ID.
        audio_url: URL of the generated audio file.
    """
    story = db.get(Story, story_id)
    if story is None:
        return
    story.audio_url = audio_url
    story.status = StoryStatus.COMPLETED
    db.commit()


def get_stories_by_user_id(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> StoryListResponse:
    """Retrieve a paginated list of stories associated with a user ID.

    Returns all stories owned by the user via their children.

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
        .where(Child.user_id == user_id)
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
    """Retrieve the single in-progress story for a user.

    Args:
        db: Database session.
        user_id: Parent user's ID.

    Returns:
        InProgressStoryResponse if a story is in progress, otherwise None.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(
            Child.user_id == user_id,
            Story.status != StoryStatus.COMPLETED,
        )
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return InProgressStoryResponse(story_id=story.id, status=story.status)


def delete_story(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a story by ID (with ownership check).

    If the story has an audio_url, the corresponding audio is also deleted
    from the TTS service before removing the DB record.

    Args:
        db: Database session.
        story_id: ID of the story to delete.
        user_id: ID of the requesting user.

    Returns:
        True if deleted, False if not found or unauthorized.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id)
    )
    story = db.scalars(stmt).first()
    if story is None:
        return False
    if story.audio_url:
        url = f"{settings.TTS_API_URL}{story.audio_url}"
        httpx.delete(url)
    db.delete(story)
    db.commit()
    return True


def get_story_audio_url(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return the audio_url for a story (with ownership check).

    Args:
        db: Database session.
        story_id: ID of the story.
        user_id: ID of the requesting user.

    Returns:
        audio_url string, or None if not found / not yet generated.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id)
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return story.audio_url


def fetch_audio_bytes(audio_url: str) -> tuple[bytes, str]:
    """Fetch audio data from the TTS service.

    Args:
        audio_url: Path returned by the TTS API (e.g. "/audio/files/xxx.mp3").
                   Combined with TTS_API_URL to form the full request URL.

    Returns:
        Tuple of (audio bytes, content_type).

    Raises:
        httpx.HTTPStatusError: If the upstream request fails.
    """
    url = f"{settings.TTS_API_URL}{audio_url}"
    response = httpx.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "audio/mpeg")
    return response.content, content_type


def get_story_by_id(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> StoryResponse | None:
    """Retrieve a single story by ID (with ownership check).

    Args:
        db: Database session.
        story_id: ID of the story to retrieve.
        user_id: ID of the requesting user. Stories belonging to other users cannot be retrieved.

    Returns:
        Story response object, or None if not found or unauthorized.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id)
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return StoryResponse.model_validate(story)


# ---------------------------------------------------------------------------
# External API stub functions (replace with real implementations)
# ---------------------------------------------------------------------------

def _call_abstract_api(theme: str) -> list[str]:
    """Call the abstract generation API.

    Args:
        theme: Story theme.

    Returns:
        List of generated abstract candidates.
    """

    """
    url = f"{settings.LLM_API_URL}/abstract/api"
    response = httpx.post(url, json={"theme": theme})
    response.raise_for_status()
    return response.json()
    """
    time.sleep(5)
    return [
        f"An exciting story about {theme} for children.",
        f"A magical adventure involving {theme}.",
        f"A brave young hero discovers the wonders of {theme}.",
    ]


def _call_story_api(theme: str, abstract: str) -> tuple[str, str]:
    """Call the story generation API.

    Args:
        theme: Story theme.
        abstract: Previously generated abstract.

    Returns:
        Tuple of (title, content).
    """
    # TODO: Replace with actual LLM API call
    time.sleep(5)
    title = f"The Adventure of {theme.capitalize()}"
    content = f"Once upon a time, {abstract} The end."
    return title, content


def _call_audio_api(story_id: str, content: str) -> str:
    """Call the audio generation API.

    Args:
        story_id: Story title.
        content: Story body text.

    Returns:
        URL of the generated audio file.
    """
    url = f"{settings.TTS_API_URL}/audio/generate"
    response = httpx.post(url, json={"text": content, story_id: story_id, })
    response.raise_for_status()
    return response.json()["audio_url"]


# ---------------------------------------------------------------------------
# Background task workers
# ---------------------------------------------------------------------------

def generate_abstract_background(story_id: uuid.UUID, theme: str) -> None:
    """Background task: generate abstract candidates and store them in cache.

    Abstracts are not saved to the DB. The client polls GET /stories/{id}/abstracts
    until status becomes abstract_ready, then the user selects one.

    Status transition: generating_abstract → abstract_ready

    Args:
        story_id: ID of the story to update.
        theme: Story theme passed to the abstract API.
    """
    db = SessionLocal()
    try:
        abstracts = _call_abstract_api(theme)
        mark_story_abstract_ready(db, story_id, abstracts)
    finally:
        db.close()


def generate_story_and_audio_background(story_id: uuid.UUID) -> None:
    """Background task: sequentially call story and audio generation APIs.

    Status transitions:
        generating_text → (story API) → generating_audio → (audio API) → completed

    Args:
        story_id: ID of the story to process.
    """
    db = SessionLocal()
    try:
        story = db.get(Story, story_id)
        if story is None:
            return

        # Step 1: generate story text
        title, content = _call_story_api(story.theme, story.abstract or "")
        update_story_content(db, story_id, title, content)

        # Step 2: generate audio
        audio_url = _call_audio_api(title, content)
        update_story_audio(db, story_id, audio_url)
    finally:
        db.close()
