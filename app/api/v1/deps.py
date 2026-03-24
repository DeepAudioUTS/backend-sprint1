import uuid

from fastapi import BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.crud.auth import get_user_by_email
from app.crud.story import (
    clear_draft_error,
    generate_abstract_background,
    generate_audio_background,
    generate_story_and_audio_background,
)
from app.db.database import get_db
from app.models.story_draft import DraftStatus, StoryDraft, get_draft_status
from app.models.user import User

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


def auto_resume_if_failed(
    draft_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> None:
    """FastAPI dependency that automatically resumes a failed story generation step.

    Inject into any draft endpoint that the client polls or interacts with.
    When the draft is in a FAILED_* state, this dependency:
      - Clears the error field (so the endpoint sees the correct in-progress status).
      - Enqueues the appropriate background task via FastAPI's BackgroundTasks
        (runs after the response is sent).

    No-ops when the draft is not found or is not in a failed state.
    """
    draft = db.get(StoryDraft, draft_id)
    if draft is None:
        return
    current_status = get_draft_status(draft)
    if current_status not in _FAILED_STATUSES:
        return

    theme = draft.theme
    clear_draft_error(db, draft_id)

    if current_status == DraftStatus.FAILED_GENERATING_ABSTRACT:
        background_tasks.add_task(generate_abstract_background, draft_id, theme)
    elif current_status == DraftStatus.FAILED_GENERATING_TEXT:
        background_tasks.add_task(generate_story_and_audio_background, draft_id)
    else:  # FAILED_GENERATING_AUDIO
        background_tasks.add_task(generate_audio_background, draft_id)
