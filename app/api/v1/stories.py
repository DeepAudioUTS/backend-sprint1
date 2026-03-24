import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.deps import auto_resume_if_failed, get_current_user
from app.crud import story as crud
from app.db.database import get_db
from app.models.story_draft import get_draft_status
from app.models.user import User
from app.schemas.story import (
    AbstractCandidate,
    AbstractSelect,
    InProgressStoryResponse,
    StoryCreate,
    StoryListResponse,
    StoryResponse,
)
from app.service import story as story_service

router = APIRouter()


@router.get("/", response_model=StoryListResponse)
def get_stories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryListResponse:
    """Return a paginated list of completed stories for the authenticated user."""
    return story_service.get_stories(db, current_user.id, limit=limit, offset=offset)


@router.post("/", response_model=InProgressStoryResponse, status_code=status.HTTP_201_CREATED)
def post_story(
    story_in: StoryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InProgressStoryResponse:
    """Create a StoryDraft and kick off abstract generation in the background.

    Returns a draft_id used for all subsequent in-progress operations.
    The Story record is created only when audio generation completes.
    """
    result = story_service.create_story(db, story_in.child_id, story_in.theme)
    background_tasks.add_task(story_service.generate_abstract_background, result.draft_id, story_in.theme)
    return result


@router.get("/in_progress", response_model=InProgressStoryResponse)
def get_in_progress_story(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InProgressStoryResponse:
    """Return the draft_id and status of the currently in-progress story.

    Status is inferred from the StoryDraft's field population.
    Returns 404 if no story is in progress.
    """
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(auto_resume_if_failed),
) -> list[AbstractCandidate]:
    """Poll for generated abstract candidates.

    Returns 200 with the list once abstracts are ready, or 202 while still generating.
    Each item contains an abstract and its paired story_prompt.
    If the draft was in a failed state, generation is automatically resumed.
    """
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=current_user.id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    if draft.abstracts is None or draft.story_prompts is None:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Abstracts are still being generated",
        )
    return [
        AbstractCandidate(abstract=a, story_prompt=sp)
        for a, sp in zip(draft.abstracts, draft.story_prompts)
    ]


@router.post("/{draft_id}/select_abstract", response_model=InProgressStoryResponse)
def post_select_abstract(
    draft_id: uuid.UUID,
    body: AbstractSelect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(auto_resume_if_failed),
) -> InProgressStoryResponse:
    """Persist the user-selected abstract and its paired story_prompt on the draft.

    Requires abstracts to be ready (ABSTRACT_READY state).
    """
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=current_user.id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    if draft.abstracts is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abstracts are not ready yet",
        )
    crud.set_selected_abstract(db, draft_id, body.abstract, body.story_prompt)
    db.refresh(draft)
    return InProgressStoryResponse(draft_id=draft.id, status=get_draft_status(draft))


@router.post(
    "/{draft_id}/generate_story",
    response_model=InProgressStoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_story(
    draft_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(auto_resume_if_failed),
) -> InProgressStoryResponse:
    """Trigger story and audio generation in the background.

    Requires an abstract to have been selected (GENERATING_TEXT state).
    When complete, the Story record is created and the draft is deleted.
    If the draft was in a failed state, generation is automatically resumed.
    """
    draft = crud.get_draft_by_id(db, draft_id=draft_id, user_id=current_user.id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    if draft.selected_abstract is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Abstract has not been selected yet",
        )
    background_tasks.add_task(story_service.generate_story_and_audio_background, draft_id)
    return InProgressStoryResponse(draft_id=draft.id, status=get_draft_status(draft))


@router.get("/{story_id}/audio")
def get_story_audio(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Fetch and return the audio file for a completed story."""
    audio_url = crud.get_story_audio_url(db, story_id=story_id, user_id=current_user.id)
    if audio_url is None:
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete a completed story by ID."""
    deleted = crud.soft_delete_story(db, story_id=story_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryResponse:
    """Return a completed story by ID."""
    story = story_service.get_story(db, story_id=story_id, user_id=current_user.id)
    if story is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return story
