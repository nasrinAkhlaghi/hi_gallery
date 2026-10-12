"""Seller persistence model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Seller(Base):
    __tablename__ = "seller"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACTIVE','SUSPENDED','REJECTED')", name="ck_seller_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("account.id"), nullable=False, unique=True)
    shop_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'PENDING'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    account: Mapped[Account] = relationship(back_populates="seller")
    products: Mapped[list[Product]] = relationship(back_populates="seller")
    seller_orders: Mapped[list[SellerOrder]] = relationship(back_populates="seller")
