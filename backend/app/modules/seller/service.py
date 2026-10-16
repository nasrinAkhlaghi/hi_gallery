"""Seller profile and application submission use cases."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Account
from app.modules.seller.models import Seller, SellerStatusHistory
from app.modules.seller.schemas import SellerProfileUpdate


class SellerProfileNotFound(Exception):
    pass


class SellerProfileNotEditable(Exception):
    pass


class SellerApplicationConflict(Exception):
    pass


class SellerOnboardingForbidden(Exception):
    pass


def _lock_seller_for_account(session: Session, account_id: UUID) -> Seller:
    seller = session.scalar(select(Seller).where(Seller.account_id == account_id).with_for_update())
    if seller is None:
        raise SellerProfileNotFound
    return seller


def get_seller_profile(session: Session, account_id: UUID) -> Seller:
    seller = session.scalar(select(Seller).where(Seller.account_id == account_id))
    if seller is None:
        raise SellerProfileNotFound
    return seller


def update_seller_profile(session: Session, account: Account, body: SellerProfileUpdate) -> Seller:
    seller = _lock_seller_for_account(session, account.id)
    if seller.status == "SUSPENDED":
        session.rollback()
        raise SellerOnboardingForbidden
    if seller.status != "DRAFT":
        session.rollback()
        raise SellerProfileNotEditable

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(seller, field, value)
    seller.updated_at = datetime.now(timezone.utc)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(seller)
    return seller


def submit_seller_application(session: Session, account: Account) -> Seller:
    seller = _lock_seller_for_account(session, account.id)
    if seller.status == "SUSPENDED":
        session.rollback()
        raise SellerOnboardingForbidden
    if seller.status != "DRAFT":
        session.rollback()
        raise SellerApplicationConflict
    if not seller.shop_name.strip():
        session.rollback()
        raise SellerApplicationConflict

    now = datetime.now(timezone.utc)
    previous_status = seller.status
    seller.status = "PENDING"
    seller.updated_at = now
    session.add(
        SellerStatusHistory(
            seller_id=seller.id,
            previous_status=previous_status,
            new_status="PENDING",
            actor_account_id=account.id,
            actor_type="SELLER",
            action="APPLICATION_SUBMITTED",
            created_at=now,
        )
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(seller)
    return seller
