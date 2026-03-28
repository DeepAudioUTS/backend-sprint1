import uuid

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.story import Story
from app.models.story_draft import StoryDraft


class Child(Base, TimestampMixin):
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
    user: Mapped[User] = relationship("User", back_populates="children")  # noqa: F821
    stories: Mapped[list[Story]] = relationship("Story", back_populates="child")  # noqa: F821
    story_draft: Mapped[StoryDraft | None] = relationship("StoryDraft", back_populates="child", uselist=False)  # noqa: F821
