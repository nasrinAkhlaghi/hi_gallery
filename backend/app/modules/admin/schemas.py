"""Typed seller review request and response DTOs."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SellerStatusFilter(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class SellerDecision(str, Enum):
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


class SellerListItem(BaseModel):
    seller_id: UUID
    shop_name: str
    seller_status: SellerStatusFilter
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


class SellerListResponse(BaseModel):
    items: list[SellerListItem]
    total: int
    page: int
    page_size: int


class SellerHistoryItem(BaseModel):
    previous_status: str | None
    new_status: str
    action: str
    timestamp: datetime
    actor_type: str
    actor_name: str | None
    reason: str | None


class SellerDetailResponse(BaseModel):
    seller_id: UUID
    shop_name: str
    description: str | None
    logo_url: str | None
    seller_status: SellerStatusFilter
    created_at: datetime
    updated_at: datetime
    history: list[SellerHistoryItem]


class SellerDecisionResponse(BaseModel):
    seller_id: UUID
    seller_status: SellerStatusFilter
    decided_at: datetime


class SellerRejectionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_and_require_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A rejection reason is required")
        if len(value) > 2000:
            raise ValueError("Rejection reason must be at most 2000 characters")
        return value
