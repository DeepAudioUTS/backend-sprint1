import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.child import Child


class User(Base, TimestampMixin):
    """User (parent) table.

    Attributes:
        id: User ID (UUID).
        name: Parent's name.
        email: Email address (unique).
        hashed_password: Hashed password.
        subscription_plan: Plan type ('free' or 'premium').
        created_at: Creation timestamp.
        updated_at: Last updated timestamp.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    subscription_plan: Mapped[str] = mapped_column(String, nullable=False, default="free")
    children: Mapped[list[Child]] = relationship("Child", back_populates="user")  # noqa: F821
