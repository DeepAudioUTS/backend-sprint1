from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings class.

    Loads values from environment variables. Falls back to the defaults
    defined in docker-compose.yml (myuser/mypassword/mydatabase) if not set.
    """

    DATABASE_URL: str = "postgresql://myuser:mypassword@db:5432/mydatabase"
    SECRET_KEY: str = "lO/H+vtMjLZHH/INONzByM4MZq/msOKFxc2JIV7DUso="
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    TTS_API_URL: str = " http://tts-api:8000"

    class Config:
        env_file = ".env"


settings = Settings()
