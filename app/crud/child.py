import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.child import Child


def get_children_by_user_id(db: Session, user_id: uuid.UUID) -> list[Child]:
    stmt = select(Child).where(Child.user_id == user_id)
    return list(db.scalars(stmt).all())
