import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.story_draft import DraftStatus


class StoryCreate(BaseModel):
    """Story creation request."""

    child_id: uuid.UUID
    theme: str


class AbstractCandidate(BaseModel):
    """A single abstract candidate returned by the LLM."""

    abstract: str
    story_prompt: str


class StoryResponse(BaseModel):
    """Story response for completed stories."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    child_id: uuid.UUID
    theme: str
    title: str | None
    abstracts: list[str] | None
    story_prompts: list[str] | None
    abstract: str | None
    story_prompt: str | None
    content: str | None
    audio_url: str | None
    created_at: datetime
    updated_at: datetime


class AbstractSelect(BaseModel):
    """Request body for selecting an abstract."""

    abstract: str
    story_prompt: str


class InProgressStoryResponse(BaseModel):
    """Response for an in-progress story.

    draft_id is the StoryDraft ID used for all in-progress operations.
    Status is inferred from the draft's field population.
    """

    draft_id: uuid.UUID
    status: DraftStatus


class StoryListResponse(BaseModel):
    """Story list response."""

    items: list[StoryResponse]
    total: int
    limit: int
    offset: int
