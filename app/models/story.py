import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class StoryStatus(str, Enum):
    """Story generation status."""

    GENERATING_ABSTRACT = "generating_abstract"
    GENERATING_TEXT = "generating_text"
    GENERATING_AUDIO = "generating_audio"
    COMPLETED = "completed"


class Story(Base):
    """Story table.

    Attributes:
        id: Story ID (UUID).
        child_id: Child ID (FK → children.id).
        theme: Story theme.
        title: Generated title.
        content: Generated story body.
        audio_url: URL of the audio file.
        status: Generation status (generating_text / generating_audio / completed).
        created_at: Creation timestamp.
        updated_at: Last updated timestamp.
    """

    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("children.id"), nullable=False, index=True
    )
    theme: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=StoryStatus.GENERATING_TEXT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    child: Mapped["Child"] = relationship("Child", back_populates="stories")  # noqa: F821
