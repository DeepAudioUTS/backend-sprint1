import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import story as crud
from app.db.database import SessionLocal
from app.models.story_draft import DraftStatus, StoryDraft, get_draft_status
from app.schemas.story import (
    AbstractCandidate,
    InProgressStoryResponse,
    StoryListResponse,
    StoryResponse,
)


# ---------------------------------------------------------------------------
# Service functions (called by the API layer)
# ---------------------------------------------------------------------------

def create_story(db: Session, child_id: uuid.UUID, theme: str) -> InProgressStoryResponse:
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


def fetch_audio_bytes(audio_url: str) -> tuple[bytes, str]:
    """Fetch audio binary data from the TTS service."""
    url = f"{settings.TTS_API_URL}{audio_url}"
    response = httpx.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "audio/mpeg")
    return response.content, content_type


# ---------------------------------------------------------------------------
# External API calls
# ---------------------------------------------------------------------------

def _call_abstract_api(theme: str) -> list[AbstractCandidate]:
    """POST to the LLM abstract generation endpoint."""
    url = f"{settings.LLM_API_URL}/api/v1/abstract/generate"
    response = httpx.post(url, json={"theme": theme, "count": 5})
    response.raise_for_status()
    return [AbstractCandidate(**item) for item in response.json()]


def _call_story_api(abstract: str, story_prompt: str) -> tuple[str, str]:
    """POST to the LLM story generation endpoint. Returns (title, content)."""
    url = f"{settings.LLM_API_URL}/api/v1/story/generate"
    response = httpx.post(url, json={"abstract": abstract, "story_prompt": story_prompt})
    response.raise_for_status()
    data = response.json()
    return data["title"], data["content"]


def _call_audio_api(file_id: uuid.UUID, content: str) -> str:
    """POST to the TTS audio generation endpoint. Returns audio_url."""
    url = f"{settings.TTS_API_URL}/audio/generate"
    response = httpx.post(url, json={"text": content, "file_id": file_id})
    response.raise_for_status()
    return response.json()["audio_url"]


# ---------------------------------------------------------------------------
# Background task workers
# ---------------------------------------------------------------------------

def generate_abstract_background(draft_id: uuid.UUID, theme: str) -> None:
    """Background task: call LLM for abstract candidates and store them on the draft.

    Draft state transition: GENERATING_ABSTRACT → ABSTRACT_READY
    On error             : GENERATING_ABSTRACT → FAILED_GENERATING_ABSTRACT
    """
    db = SessionLocal()
    try:
        candidates = _call_abstract_api(theme)
        abstracts = [c.abstract for c in candidates]
        story_prompts = [c.story_prompt for c in candidates]
        crud.mark_abstract_ready(db, draft_id, abstracts, story_prompts)
    except Exception as e:
        crud.mark_failed(db, draft_id, str(e))
    finally:
        db.close()


def generate_story_and_audio_background(draft_id: uuid.UUID) -> None:
    """Background task: call LLM for story text, then TTS for audio.

    Draft state transitions:
        GENERATING_TEXT  → (LLM)  → GENERATING_AUDIO → (TTS) → Story created, draft deleted
        On LLM error  → FAILED_GENERATING_TEXT
        On TTS error  → FAILED_GENERATING_AUDIO
    """
    db = SessionLocal()
    try:
        draft = db.get(StoryDraft, draft_id)
        if draft is None:
            return

        try:
            title, content = _call_story_api(
                draft.selected_abstract or "", draft.selected_story_prompt or ""
            )
        except Exception as e:
            crud.mark_failed(db, draft_id, str(e))
            return
        crud.set_story_content(db, draft_id, title, content)

        try:
            audio_url = _call_audio_api(draft_id, content)
        except Exception as e:
            crud.mark_failed(db, draft_id, str(e))
            return
        crud.finalize_story(db, draft_id, audio_url)
    finally:
        db.close()


def generate_audio_background(draft_id: uuid.UUID) -> None:
    """Background task: call TTS for audio only (retry of FAILED_GENERATING_AUDIO).

    Draft state transition: GENERATING_AUDIO → Story created, draft deleted
    On error             : GENERATING_AUDIO → FAILED_GENERATING_AUDIO
    """
    db = SessionLocal()
    try:
        draft = db.get(StoryDraft, draft_id)
        if draft is None:
            return
        try:
            audio_url = _call_audio_api(draft.title or "", draft.generated_text or "")
        except Exception as e:
            crud.mark_failed(db, draft_id, str(e))
            return
        crud.finalize_story(db, draft_id, audio_url)
    finally:
        db.close()
