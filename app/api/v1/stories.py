import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import Response

from app.api.v1.deps import CurrentUser, DBSession
from app.exceptions import ConflictError, NotFoundError, StillProcessingError
from app.schemas.story import (
    AbstractCandidate,
    AbstractSelect,
    InProgressStoryResponse,
    StoryCreate,
    StoryListResponse,
    StoryResponse,
)
from app.service import story as story_service
from app.tasks import story as story_tasks

router = APIRouter()


@router.get("/", response_model=StoryListResponse)
def get_stories(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> StoryListResponse:
    """Return a paginated list of completed stories for the authenticated user."""
    return story_service.get_stories(db, current_user.id, limit=limit, offset=offset)


@router.post("/", response_model=InProgressStoryResponse, status_code=status.HTTP_201_CREATED)
def post_story(
    story_in: StoryCreate,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> InProgressStoryResponse:
    """Create a StoryDraft and kick off abstract generation in the background."""
    result = story_service.create_story_draft(db, story_in.child_id, story_in.theme)
    background_tasks.add_task(story_tasks.generate_abstract_background, result.draft_id, story_in.theme)
    return result


@router.get("/in_progress", response_model=InProgressStoryResponse)
def get_in_progress_story(
    current_user: CurrentUser,
    db: DBSession,
) -> InProgressStoryResponse:
    """Return the draft_id and status of the currently in-progress story."""
    result = story_service.get_in_progress_story(db, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No story in progress",
        )
    return result


@router.get("/{draft_id}/abstracts", response_model=list[AbstractCandidate])
def get_abstracts(
    draft_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[AbstractCandidate]:
    """Poll for generated abstract candidates."""
    try:
        return story_service.get_abstracts(db, draft_id=draft_id, user_id=current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    except StillProcessingError:
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Abstracts are still being generated")


@router.post("/{draft_id}/select_abstract", response_model=InProgressStoryResponse)
def post_select_abstract(
    draft_id: uuid.UUID,
    body: AbstractSelect,
    current_user: CurrentUser,
    db: DBSession,
) -> InProgressStoryResponse:
    """Persist the user-selected abstract and its paired story_prompt on the draft."""
    try:
        return story_service.select_abstract(
            db,
            draft_id=draft_id,
            abstract=body.abstract,
            story_prompt=body.story_prompt,
            user_id=current_user.id,
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{draft_id}/generate_story",
    response_model=InProgressStoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_story(
    draft_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DBSession,
) -> InProgressStoryResponse:
    """Trigger story and audio generation in the background."""
    try:
        result = story_service.prepare_generate_story(db, draft_id=draft_id, user_id=current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    background_tasks.add_task(story_tasks.generate_story_and_audio_background, draft_id)
    return result


@router.get("/{story_id}/audio")
def get_story_audio(
    story_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Response:
    """Fetch and return the audio file for a completed story."""
    try:
        audio_url = story_service.get_story_audio_url(db, story_id=story_id, user_id=current_user.id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found or audio not yet generated",
        )
    try:
        audio_bytes, content_type = story_service.fetch_audio_bytes(audio_url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch audio from TTS service: {e.response.status_code}",
        )
    return Response(content=audio_bytes, media_type=content_type)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story_endpoint(
    story_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Soft-delete a completed story by ID."""
    try:
        story_service.delete_story(db, story_id=story_id, user_id=current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> StoryResponse:
    """Return a completed story by ID."""
    story = story_service.get_story(db, story_id=story_id, user_id=current_user.id)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return story
