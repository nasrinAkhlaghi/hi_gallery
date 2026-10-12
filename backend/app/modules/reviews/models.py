"""Review persistence model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Review(Base):
    __tablename__ = "review"
    __table_args__ = (
        UniqueConstraint("buyer_id", "product_id", "order_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
        Index("idx_review_product", "product_id"),
        Index("idx_review_buyer", "buyer_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    buyer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("buyer.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("product.id"), nullable=False)
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    buyer: Mapped[Buyer] = relationship(back_populates="reviews")
    product: Mapped[Product] = relationship(back_populates="reviews")
    order: Mapped[Order] = relationship(back_populates="reviews")
