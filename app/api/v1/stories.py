import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.crud.story import (
    create_story,
    get_stories_by_user_id,
    get_story_by_id,
    update_story_generated_text,
)
from app.db.database import get_db
from app.models.user import User
from app.schemas.story import StoryCreate, StoryListResponse, StoryResponse
from app.tool.story_generator import generate_story_content, sanitize_provider_error

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryResponse:
    """Create a new story."""
    return create_story(db, story_in)


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


class GenerateStoryRequest(BaseModel):
    storyTemplate: str
    eduContent: str
    model: str
    token: str
    story_id: uuid.UUID | None = None
    request_timeout: int = 180
    temperature: float = 0.7


class GenerateStoryResponse(BaseModel):
    role: str
    content: str
    story_id: uuid.UUID | None = None


def _extract_title(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        candidate = re.sub(r"^#+\s*", "", stripped).strip()
        return candidate[:120] if candidate else None
    return None


@router.post("/GenerateStory", response_model=GenerateStoryResponse)
def generate_story(
    payload: GenerateStoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerateStoryResponse:
    if not payload.token:
        raise HTTPException(status_code=400, detail="token is required")

    if not payload.model:
        raise HTTPException(status_code=400, detail="model is required")

    try:
        content = generate_story_content(
            token=payload.token,
            model=payload.model,
            story_template=payload.storyTemplate,
            edu_content=payload.eduContent,
            temperature=payload.temperature,
            request_timeout=payload.request_timeout,
        )
    except KeyError as exc:
        missing_key = str(exc).strip("'")
        raise HTTPException(
            status_code=400,
            detail=(
                f"storyTemplate contains unknown placeholder '{missing_key}'. "
                "Use '{eduContent}' or '{EducationMaterial}', or escape braces as '{{' and '}}'."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="storyTemplate has invalid format braces. Escape literal braces as '{{' and '}}'.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        safe_message = sanitize_provider_error(exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed: {safe_message}",
        ) from exc

    if payload.story_id:
        updated_story = update_story_generated_text(
            db,
            story_id=payload.story_id,
            user_id=current_user.id,
            content=content,
            title=_extract_title(content),
        )
        if updated_story is None:
            raise HTTPException(status_code=404, detail="Story not found")

    return GenerateStoryResponse(
        role="assistant",
        content=content,
        story_id=payload.story_id,
    )
