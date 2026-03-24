import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DraftStatus(str, Enum):
    """Story generation status inferred from StoryDraft field population."""

    GENERATING_ABSTRACT = "generating_abstract"
    ABSTRACT_READY = "abstract_ready"
    GENERATING_TEXT = "generating_text"
    GENERATING_AUDIO = "generating_audio"


def get_draft_status(draft: "StoryDraft") -> DraftStatus:
    """Infer the current generation status from which fields are populated."""
    if draft.generated_text is not None:
        return DraftStatus.GENERATING_AUDIO
    if draft.selected_abstract is not None:
        return DraftStatus.GENERATING_TEXT
    if draft.abstracts is not None:
        return DraftStatus.ABSTRACT_READY
    return DraftStatus.GENERATING_ABSTRACT


class StoryDraft(Base):
    """Temporary storage for in-progress story generation.

    Holds intermediate data during story creation (abstract candidates,
    selected abstract, generated text). Deleted when the story is finalized.
    Enforces 1:1 with Child via unique constraint.

    Status is not stored — it is inferred from which fields are populated
    via get_draft_status(). Progression:
        abstracts=None            → GENERATING_ABSTRACT
        abstracts set             → ABSTRACT_READY
        selected_abstract set     → GENERATING_TEXT
        generated_text set        → GENERATING_AUDIO
        (draft deleted)           → completed

    Attributes:
        id: Draft ID (UUID).
        child_id: Child ID (FK → children.id, unique).
        theme: Story theme provided by the user.
        title: Generated story title.
        abstracts: List of abstract candidates from LLM.
        selected_abstract: Abstract chosen by the user.
        generated_text: Generated story body text.
        created_at: Creation timestamp.
        updated_at: Last updated timestamp.
    """

    __tablename__ = "story_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("children.id"), nullable=False, unique=True, index=True
    )
    theme: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    abstracts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    story_prompts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    selected_abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_story_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    child: Mapped["Child"] = relationship("Child", back_populates="story_draft")  # noqa: F821
