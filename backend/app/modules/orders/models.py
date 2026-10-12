"""Order, seller order, and order item persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    and_,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.session import Base
from app.modules.products.models import Product


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_orders_total_amount"),
        CheckConstraint(
            "status IN ('PENDING','PAID','PROCESSING','SHIPPED','DELIVERED','CANCELLED','REFUNDED')",
            name="ck_orders_status",
        ),
        Index("idx_orders_buyer", "buyer_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    buyer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("buyer.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'PENDING'"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_name: Mapped[str] = mapped_column(String(150), nullable=False)
    shipping_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    buyer: Mapped[Buyer] = relationship(back_populates="orders")
    seller_orders: Mapped[list[SellerOrder]] = relationship(back_populates="order")
    payments: Mapped[list[Payment]] = relationship(back_populates="order")
    reviews: Mapped[list[Review]] = relationship(back_populates="order")


class SellerOrder(Base):
    __tablename__ = "seller_order"
    __table_args__ = (
        UniqueConstraint("order_id", "seller_id"),
        UniqueConstraint("id", "seller_id"),
        CheckConstraint("subtotal >= 0", name="ck_seller_order_subtotal"),
        CheckConstraint("shipping_amount >= 0", name="ck_seller_order_shipping"),
        CheckConstraint("commission_amount >= 0", name="ck_seller_order_commission"),
        CheckConstraint("seller_amount >= 0", name="ck_seller_order_seller_amount"),
        CheckConstraint(
            "status IN ('PENDING','PAID','PROCESSING','SHIPPED','DELIVERED','CANCELLED','REFUNDED')",
            name="ck_seller_order_status",
        ),
        Index("idx_seller_order_seller", "seller_id"),
        Index("idx_seller_order_order", "order_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    seller_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("seller.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'PENDING'"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    seller_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    order: Mapped[Order] = relationship(back_populates="seller_orders")
    seller: Mapped[Seller] = relationship(back_populates="seller_orders")
    order_items: Mapped[list[OrderItem]] = relationship(
        back_populates="seller_order",
        foreign_keys="[OrderItem.seller_order_id, OrderItem.seller_id]",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["seller_order_id", "seller_id"],
            ["seller_order.id", "seller_order.seller_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["product_id", "seller_id"], ["product.id", "product.seller_id"]),
        CheckConstraint("unit_price >= 0", name="ck_order_item_price"),
        CheckConstraint("quantity > 0", name="ck_order_item_quantity"),
        Index("idx_order_item_seller_order", "seller_order_id"),
        Index("idx_order_item_product", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    seller_order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    seller_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    seller_order: Mapped[SellerOrder] = relationship(
        back_populates="order_items", foreign_keys=[seller_order_id, seller_id]
    )
    product: Mapped[Product] = relationship(
        back_populates="order_items",
        primaryjoin=lambda: and_(
            Product.id == foreign(OrderItem.product_id),
            Product.seller_id == OrderItem.seller_id,
        ),
    )
