"""Seller product contracts; prices remain decimal strings on the wire."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProductStatus = Literal["DRAFT", "ACTIVE", "INACTIVE", "SOLD_OUT"]


class ProductWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    category_id: UUID
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    stock: int = Field(ge=0, le=2_147_483_647, strict=True)
    status: ProductStatus = "DRAFT"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str
    sort_order: int


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category_id: UUID
    name: str
    description: str | None
    price: Decimal
    stock: int
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    images: list[ImageResponse]


class ProductList(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    parent_id: UUID | None
    name: str
    slug: str


class CategoryList(BaseModel):
    items: list[CategoryResponse]
    total: int
    page: int
    page_size: int


class PublicSellerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    shop_name: str


class PublicProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    category: CategoryResponse
    price: Decimal
    stock: int
    status: Literal["ACTIVE", "SOLD_OUT"]
    images: list[ImageResponse]
    seller: PublicSellerResponse


class PublicProductList(BaseModel):
    items: list[PublicProductResponse]
    total: int
    page: int
    page_size: int
