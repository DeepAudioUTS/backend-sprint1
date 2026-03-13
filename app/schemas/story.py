import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.story import StoryStatus


class StoryCreate(BaseModel):
    """Story creation request."""

    child_id: uuid.UUID
    theme: str


class StoryResponse(BaseModel):
    """Story response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    child_id: uuid.UUID
    theme: str
    title: str | None
    content: str | None
    audio_url: str | None
    status: StoryStatus
    created_at: datetime
    updated_at: datetime


class StoryListResponse(BaseModel):
    """Story list response."""

    items: list[StoryResponse]
    total: int
    limit: int
    offset: int
