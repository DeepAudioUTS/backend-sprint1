from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser, DBSession
from app.db.session import get_db
from app.models.user import User
from app.schemas.child import ChildResponse
from app.service import child as child_service

router = APIRouter()


@router.get("/", response_model=list[ChildResponse])
def get_children(
    current_user: User = CurrentUser,
    db: Session = DBSession,
) -> list[ChildResponse]:
    """Return the list of children associated with the authenticated user."""
    return child_service.get_children(db, current_user.id)
