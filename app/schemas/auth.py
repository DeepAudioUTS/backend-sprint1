from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str
    token_type: str = "bearer"
