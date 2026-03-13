import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.child import Child
from app.models.story import Story, StoryStatus
from app.schemas.story import StoryCreate, StoryResponse, StoryListResponse


def create_story(db: Session, story_in: StoryCreate) -> StoryResponse:
    """Create a new story.

    Status is initialized to generating_text.

    Args:
        db: Database session.
        story_in: Story creation request (child_id, theme).

    Returns:
        Response object of the created story.
    """
    story = Story(
        child_id=story_in.child_id,
        theme=story_in.theme,
        status=StoryStatus.GENERATING_TEXT,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return StoryResponse.model_validate(story)


def get_stories_by_user_id(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> StoryListResponse:
    """Retrieve a paginated list of stories associated with a user ID.

    Returns all stories owned by the user via their children.

    Args:
        db: Database session.
        user_id: Parent user's ID.
        limit: Maximum number of results to return.
        offset: Starting position for retrieval.

    Returns:
        Response object containing the story list and count metadata.
    """
    base_stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Child.user_id == user_id)
    )

    total: int = db.scalar(
        select(func.count()).select_from(base_stmt.subquery())
    ) or 0

    stories = db.scalars(
        base_stmt.order_by(Story.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return StoryListResponse(
        items=[StoryResponse.model_validate(s) for s in stories],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_story_by_id(
    db: Session, story_id: uuid.UUID, user_id: uuid.UUID
) -> StoryResponse | None:
    """Retrieve a single story by ID (with ownership check).

    Args:
        db: Database session.
        story_id: ID of the story to retrieve.
        user_id: ID of the requesting user. Stories belonging to other users cannot be retrieved.

    Returns:
        Story response object, or None if not found or unauthorized.
    """
    stmt = (
        select(Story)
        .join(Child, Story.child_id == Child.id)
        .where(Story.id == story_id, Child.user_id == user_id)
    )
    story = db.scalars(stmt).first()
    if story is None:
        return None
    return StoryResponse.model_validate(story)
