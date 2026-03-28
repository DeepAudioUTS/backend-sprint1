from jose import JWTError
from sqlalchemy.orm import Session

from app import crud
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.exceptions import DuplicateEmailError, InvalidCredentialsError, InvalidTokenError
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


def register(db: Session, payload: UserCreate) -> TokenResponse:
    if crud.user.get_by_email(db, payload.email):
        raise DuplicateEmailError()
    user = crud.user.create(db, email=payload.email, hashed_password=hash_password(payload.password))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


def login(db: Session, email: str, password: str) -> TokenResponse:
    user = crud.user.get_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


def refresh(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError()
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise InvalidTokenError()
    except JWTError:
        raise InvalidTokenError()

    user = crud.user.get_by_id(db, int(user_id))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
