from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DBSession
from app.schemas.child import ChildResponse
from app.service import child as child_service

router = APIRouter()


@router.get("/", response_model=list[ChildResponse])
def get_children(
    current_user: CurrentUser,
    db: DBSession,
) -> list[ChildResponse]:
    """Return the list of children associated with the authenticated user."""
    return child_service.get_children(db, current_user.id)
