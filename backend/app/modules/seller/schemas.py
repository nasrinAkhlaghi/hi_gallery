"""Validated seller onboarding inputs and safe response DTOs."""

from datetime import datetime
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SellerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shop_name: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    logo_url: str | None = Field(default=None, max_length=2_048)

    @field_validator("shop_name")
    @classmethod
    def validate_shop_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Shop name is required")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Shop name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Logo URL must be an absolute HTTP(S) URL")
        return normalized

    @model_validator(mode="after")
    def require_update_fields(self) -> "SellerProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be supplied")
        return self


class SellerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shop_name: str
    description: str | None
    logo_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SellerApplicationResponse(BaseModel):
    status: str
    can_edit: bool
    can_submit: bool
    rejection_reason: str | None = None
