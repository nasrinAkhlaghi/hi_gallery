"""Buyer persistence model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Buyer(Base):
    __tablename__ = "buyer"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("account.id"), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    account: Mapped[Account] = relationship(back_populates="buyer")
    cart: Mapped[Cart | None] = relationship(back_populates="buyer", uselist=False)
    orders: Mapped[list[Order]] = relationship(back_populates="buyer")
    reviews: Mapped[list[Review]] = relationship(back_populates="buyer")
