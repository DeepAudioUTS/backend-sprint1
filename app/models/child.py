import uuid
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Child(Base):
    """Child table.

    Attributes:
        id: Child ID (UUID).
        user_id: Parent user ID (FK → users.id).
        name: Child's name.
        age: Child's age.
        created_at: Creation timestamp.
        updated_at: Last updated timestamp.
    """

    __tablename__ = "children"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="children")  # noqa: F821
    stories: Mapped[list["Story"]] = relationship("Story", back_populates="child")  # noqa: F821
    story_draft: Mapped["StoryDraft | None"] = relationship("StoryDraft", back_populates="child", uselist=False)  # noqa: F821
