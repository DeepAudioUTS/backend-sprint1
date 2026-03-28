import uuid

from sqlalchemy.orm import Session

from app.crud import child as crud
from app.schemas.child import ChildResponse


def get_children(db: Session, user_id: uuid.UUID) -> list[ChildResponse]:
    children = crud.get_children_by_user_id(db, user_id)
    return [ChildResponse.model_validate(c) for c in children]
