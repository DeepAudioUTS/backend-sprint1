import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.crud.story import (
    create_story,
    generate_abstract_background,
    generate_story_and_audio_background,
    get_stories_by_user_id,
    get_story_by_id,
)
from app.db.database import get_db
from app.models.story import StoryStatus
from app.models.user import User
from app.schemas.story import StoryCreate, StoryListResponse, StoryResponse

router = APIRouter()


@router.get("/", response_model=StoryListResponse)
def get_stories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryListResponse:
    """Return a paginated list of stories for the authenticated user."""
    return get_stories_by_user_id(db, current_user.id, limit=limit, offset=offset)


@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def post_story(
    story_in: StoryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryResponse:
    """Create a new story and kick off abstract generation in the background.

    Status after this call: generating_abstract
    After background task completes: generating_text
    """
    story = create_story(db, story_in)
    background_tasks.add_task(generate_abstract_background, story.id, story.theme)
    return story


@router.post(
    "/{story_id}/generate_story",
    response_model=StoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_story(
    story_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryResponse:
    """Trigger story and audio generation for a story whose abstract is ready.

    The story must be in generating_text status (abstract already generated).
    Story generation and audio generation run sequentially in the background.

    Status transitions:
        generating_text → (story API) → generating_audio → (audio API) → completed
    """
    story = get_story_by_id(db, story_id=story_id, user_id=current_user.id)
    if story is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    if story.status != StoryStatus.GENERATING_TEXT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Story is not ready for generation (current status: {story.status})",
        )
    background_tasks.add_task(generate_story_and_audio_background, story_id)
    return story


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryResponse:
    """Return the story with the specified ID (stories of other users cannot be retrieved)."""
    story = get_story_by_id(db, story_id=story_id, user_id=current_user.id)
    if story is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return story
