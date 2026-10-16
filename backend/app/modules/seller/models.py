"""Seller persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Account
    from app.modules.orders.models import SellerOrder
    from app.modules.products.models import Product


class Seller(Base):
    __tablename__ = "seller"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')", name="ck_seller_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("account.id"), nullable=False, unique=True)
    shop_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'DRAFT'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    account: Mapped[Account] = relationship(back_populates="seller")
    products: Mapped[list[Product]] = relationship(back_populates="seller")
    seller_orders: Mapped[list[SellerOrder]] = relationship(back_populates="seller")
    status_history: Mapped[list[SellerStatusHistory]] = relationship(
        back_populates="seller", order_by="SellerStatusHistory.created_at"
    )


class SellerStatusHistory(Base):
    """Append-only record of seller lifecycle events."""

    __tablename__ = "seller_status_history"
    __table_args__ = (
        Index("ix_seller_status_history_seller_created", "seller_id", "created_at"),
        Index("ix_seller_status_history_actor_account", "actor_account_id"),
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')",
            name="ck_seller_status_history_previous_status",
        ),
        CheckConstraint(
            "new_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')",
            name="ck_seller_status_history_new_status",
        ),
        CheckConstraint("actor_type IN ('SELLER','ADMIN')", name="ck_seller_status_history_actor_type"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    seller_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("seller.id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("account.id"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    seller: Mapped[Seller] = relationship(back_populates="status_history")
