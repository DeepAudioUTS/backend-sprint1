from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.crud.child import get_children_by_user_id
from app.db.database import get_db
from app.models.user import User
from app.schemas.child import ChildResponse

router = APIRouter()


@router.get("/", response_model=list[ChildResponse])
def get_children(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChildResponse]:
    """Return the list of children associated with the authenticated user."""
    return get_children_by_user_id(db, current_user.id)
