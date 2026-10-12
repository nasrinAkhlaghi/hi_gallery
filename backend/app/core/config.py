"""Environment-based application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings loaded from environment variables and the repository .env file."""

    database_url: str

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        if any(error["loc"] == ("database_url",) for error in exc.errors()):
            raise RuntimeError(
                "DATABASE_URL is required. Set it in the environment or in the repository .env file."
            ) from exc
        raise
