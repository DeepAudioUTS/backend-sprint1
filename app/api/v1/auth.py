from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.security import create_access_token
from app.crud.auth import authenticate_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate with email and password and return a JWT token."""
    user = authenticate_user(db, request.email, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.email)
    return LoginResponse(access_token=access_token)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """Log out (the client is responsible for discarding the token)."""
    return {"message": "Successfully logged out"}
