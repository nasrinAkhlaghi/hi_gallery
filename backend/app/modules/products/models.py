"""Product and product image persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price"),
        CheckConstraint("stock >= 0", name="ck_product_stock"),
        CheckConstraint("status IN ('DRAFT','ACTIVE','INACTIVE','SOLD_OUT')", name="ck_product_status"),
        UniqueConstraint("id", "seller_id", name="uk_product_id_seller"),
        Index("idx_product_seller", "seller_id"),
        Index("idx_product_category", "category_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    seller_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("seller.id"), nullable=False)
    category_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("category.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'DRAFT'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    seller: Mapped[Seller] = relationship(back_populates="products")
    category: Mapped[Category] = relationship(back_populates="products")
    images: Mapped[list[ProductImage]] = relationship(back_populates="product", cascade="all, delete-orphan")
    cart_items: Mapped[list[CartItem]] = relationship(back_populates="product")
    order_items: Mapped[list[OrderItem]] = relationship(
        back_populates="product",
        primaryjoin="and_(Product.id == foreign(OrderItem.product_id), Product.seller_id == OrderItem.seller_id)",
    )
    reviews: Mapped[list[Review]] = relationship(back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_image"
    __table_args__ = (CheckConstraint("sort_order >= 0", name="ck_product_image_sort_order"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    product: Mapped[Product] = relationship(back_populates="images")
