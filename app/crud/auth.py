from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_email(db: Session, email: str) -> User | None:
    """Retrieve a user by email address.

    Args:
        db: Database session.
        email: Email address to search for.

    Returns:
        The matching user, or None if not found.
    """
    stmt = select(User).where(User.email == email)
    return db.scalars(stmt).first()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hashed password.

    Args:
        plain_password: Plain-text password provided by the user.
        hashed_password: Hashed password stored in the database.

    Returns:
        True if they match.
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password.

    Args:
        plain_password: Plain-text password to hash.

    Returns:
        Hashed password string.
    """
    return pwd_context.hash(plain_password)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Authenticate a user by email address and password.

    Args:
        db: Database session.
        email: Email address for login.
        password: Plain-text password provided by the user.

    Returns:
        User object on success, or None on failure.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
