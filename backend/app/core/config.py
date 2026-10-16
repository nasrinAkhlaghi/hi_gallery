"""Environment-based application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings loaded from environment variables and the repository .env file."""

    database_url: str
    jwt_signing_key: SecretStr
    csrf_signing_key: SecretStr
    auth_issuer: str = "https://api.hi-gallery.local"
    auth_audience: str = "hi-gallery-web"
    environment: Literal["development", "test", "production"] = "development"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_signing_key", "csrf_signing_key")
    @classmethod
    def validate_signing_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("Signing keys must contain at least 32 bytes")
        return value

    @field_validator("auth_issuer", "auth_audience")
    @classmethod
    def validate_auth_claim_setting(cls, value: str) -> str:
        value = value.strip()
        if not value or value == "*":
            raise ValueError("Issuer and audience must be explicit non-empty values")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise ValueError("CORS origins must be an explicit comma-separated allowlist")
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
                raise ValueError(f"Invalid CORS origin: {origin}")
        return ",".join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return self.cors_allowed_origins.split(",")

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"


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
