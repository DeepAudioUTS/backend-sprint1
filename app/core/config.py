from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings class.

    Loads values from environment variables. Falls back to the defaults
    defined in docker-compose.yml (myuser/mypassword/mydatabase) if not set.
    """

    DATABASE_URL: str = "postgresql://myuser:mypassword@db:5432/mydatabase"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    class Config:
        env_file = ".env"


settings = Settings()
