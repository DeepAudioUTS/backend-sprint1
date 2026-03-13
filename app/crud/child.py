import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.child import Child
from app.schemas.child import ChildResponse


def get_children_by_user_id(db: Session, user_id: uuid.UUID) -> list[ChildResponse]:
    """Retrieve the list of children associated with a user ID.

    Args:
        db: Database session.
        user_id: Parent user's ID.

    Returns:
        List of child response objects.
    """
    stmt = select(Child).where(Child.user_id == user_id)
    children = db.scalars(stmt).all()
    return [ChildResponse.model_validate(child) for child in children]
