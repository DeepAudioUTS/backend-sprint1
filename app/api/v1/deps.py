import uuid

from fastapi import BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.crud.auth import get_user_by_email
from app.crud import story as crud
from app.db.database import get_db
from app.models.story_draft import DraftStatus, get_draft_status
from app.models.user import User
from app.service import story as story_service

_FAILED_STATUSES = frozenset({
    DraftStatus.FAILED_GENERATING_ABSTRACT,
    DraftStatus.FAILED_GENERATING_TEXT,
    DraftStatus.FAILED_GENERATING_AUDIO,
})

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that retrieves the authenticated user.

    Validates the Bearer token from the Authorization header and returns the corresponding user.

    Args:
        token: JWT token obtained from the OAuth2 scheme.
        db: Database session.

    Returns:
        Authenticated user object.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
    """
    email = decode_access_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _resume_draft(
    draft: "StoryDraft",  # noqa: F821
    db: Session,
    background_tasks: BackgroundTasks,
) -> None:
    """Resume a draft that is in a FAILED_* state. No-ops for any other state."""
    current_status = get_draft_status(draft)
    if current_status not in _FAILED_STATUSES:
        return

    draft_id = draft.id
    theme = draft.theme
    crud.clear_error(db, draft_id)

    if current_status == DraftStatus.FAILED_GENERATING_ABSTRACT:
        background_tasks.add_task(story_service.generate_abstract_background, draft_id, theme)
    elif current_status == DraftStatus.FAILED_GENERATING_TEXT:
        background_tasks.add_task(story_service.generate_story_and_audio_background, draft_id)
    else:  # FAILED_GENERATING_AUDIO
        background_tasks.add_task(story_service.generate_audio_background, draft_id)


def auto_resume_if_failed(
    draft_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> None:
    """Dependency for draft endpoints with {draft_id} in the path.

    Looks up the draft by draft_id and resumes it if it is in a FAILED_* state.
    """
    draft = crud.get_draft(db, draft_id)
    if draft is None:
        return
    _resume_draft(draft, db, background_tasks)


def auto_resume_in_progress(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Dependency for GET /in_progress.

    Looks up the user's active draft and resumes it if it is in a FAILED_* state.
    """
    draft = crud.get_active_draft_by_user(db, current_user.id)
    if draft is None:
        return
    _resume_draft(draft, db, background_tasks)
