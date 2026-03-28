import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import story as crud
from app.exceptions import ConflictError, NotFoundError, StillProcessingError
from app.models.story_draft import DraftStatus, get_draft_status
from app.schemas.story import (
    AbstractCandidate,
    InProgressStoryResponse,
    StoryListResponse,
    StoryResponse,
)

# ---------------------------------------------------------------------------
# Service functions (called by the API layer)
# ---------------------------------------------------------------------------

def create_story_draft(db: Session, child_id: uuid.UUID, theme: str) -> InProgressStoryResponse:
    """Create a StoryDraft and return the initial in-progress response."""
    draft = crud.create_draft(db, child_id=child_id, theme=theme)
    return InProgressStoryResponse(draft_id=draft.id, status=DraftStatus.GENERATING_ABSTRACT)


def get_in_progress_story(db: Session, user_id: uuid.UUID) -> InProgressStoryResponse | None:
    """Return the in-progress story status for a user, or None."""
    draft = crud.get_active_draft_by_user(db, user_id)
    if draft is None:
        return None
    return InProgressStoryResponse(
        draft_id=draft.id,
        status=get_draft_status(draft),
        error=draft.error,
    )


def get_stories(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> StoryListResponse:
    """Return a paginated list of completed stories for a user."""
    stories, total = crud.get_stories(db, user_id, limit, offset)
    return StoryListResponse(
        items=[StoryResponse.model_validate(s) for s in stories],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_story(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> StoryResponse | None:
    """Return a single completed story, or None."""
    story = crud.get_story_by_id(db, story_id, user_id)
    if story is None:
        return None
    return StoryResponse.model_validate(story)


def get_abstracts(
    db: Session, draft_id: uuid.UUID, user_id: uuid.UUID
) -> list[AbstractCandidate]:
    """Return abstract candidates for a draft, or raise if not ready / not found."""
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=user_id)
    if draft is None:
        raise NotFoundError()
    if draft.abstracts is None or draft.story_prompts is None:
        raise StillProcessingError()
    return [
        AbstractCandidate(abstract=a, story_prompt=sp)
        for a, sp in zip(draft.abstracts, draft.story_prompts)
    ]


def select_abstract(
    db: Session,
    draft_id: uuid.UUID,
    abstract: str,
    story_prompt: str,
    user_id: uuid.UUID,
) -> InProgressStoryResponse:
    """Persist the selected abstract and return the updated draft status."""
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=user_id)
    if draft is None:
        raise NotFoundError()
    if draft.abstracts is None:
        raise ConflictError("Abstracts are not ready yet")
    crud.set_selected_abstract(db, draft_id, abstract, story_prompt)
    db.refresh(draft)
    return InProgressStoryResponse(draft_id=draft.id, status=get_draft_status(draft))


def prepare_generate_story(
    db: Session, draft_id: uuid.UUID, user_id: uuid.UUID
) -> InProgressStoryResponse:
    """Validate the draft is ready for story generation and return its status."""
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=user_id)
    if draft is None:
        raise NotFoundError()
    if draft.selected_abstract is None:
        raise ConflictError("Abstract has not been selected yet")
    return InProgressStoryResponse(draft_id=draft.id, status=get_draft_status(draft))


def get_story_audio_url(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> str:
    """Return the audio URL for a story, or raise NotFoundError."""
    audio_url = crud.get_story_audio_url(db, story_id=story_id, user_id=user_id)
    if audio_url is None:
        raise NotFoundError()
    return audio_url


def delete_story(db: Session, story_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Soft-delete a story, or raise NotFoundError."""
    deleted = crud.soft_delete_story(db, story_id=story_id, user_id=user_id)
    if not deleted:
        raise NotFoundError()


def fetch_audio_bytes(audio_url: str) -> tuple[bytes, str]:
    """Fetch audio binary data from the TTS service."""
    url = f"{settings.TTS_API_URL}{audio_url}"
    response = httpx.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "audio/mpeg")
    return response.content, content_type
