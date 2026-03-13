import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChildResponse(BaseModel):
    """Child response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: int
    created_at: datetime
    updated_at: datetime
