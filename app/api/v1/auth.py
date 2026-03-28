from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.deps import DBSession
from app.exceptions import InactiveUserError, InvalidCredentialsError, InvalidTokenError
from app.schemas.auth import RefreshRequest, TokenResponse
from app.schemas.user import UserCreate
from app.exceptions import DuplicateEmailError
from app import service

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DBSession):
    try:
        return service.auth.register(db, payload)
    except DuplicateEmailError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


@router.post("/login", response_model=TokenResponse)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession):
    try:
        return service.auth.login(db, email=form.username, password=form.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except InactiveUserError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DBSession):
    try:
        return service.auth.refresh(db, payload.refresh_token)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
