"""Seller profile and application submission use cases."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Account
from app.modules.categories.models import Category
from app.modules.seller.models import Seller, SellerStatusHistory
from app.modules.seller.schemas import SellerProfileUpdate, SellerShopUpdate


class SellerProfileNotFound(Exception):
    pass


class SellerProfileNotEditable(Exception):
    pass


class SellerApplicationConflict(Exception):
    pass


class SellerOnboardingForbidden(Exception):
    pass


class SellerShopForbidden(Exception):
    pass


class ShopCategoryUnavailable(Exception):
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


def public_seller_conditions():
    """Shared eligibility for public shops and all public product queries."""
    return (Seller.status == "ACTIVE", Account.status == "ACTIVE")


def get_public_shop(session: Session, seller_id: UUID) -> dict:
    seller = session.scalar(
        select(Seller).join(Account, Account.id == Seller.account_id)
        .where(Seller.id == seller_id, *public_seller_conditions())
    )
    if seller is None:
        raise SellerProfileNotFound
    category = session.get(Category, seller.shop_category_id) if seller.shop_category_id is not None else None
    return {
        "id": seller.id, "shop_name": seller.shop_name, "description": seller.description,
        "logo_url": seller.logo_url, "theme_id": seller.theme_id,
        "category": category if category is not None and category.status == "ACTIVE" else None,
    }


def update_seller_shop(session: Session, account: Account, body: SellerShopUpdate) -> Seller:
    try:
        seller = session.scalar(
            select(Seller).where(Seller.account_id == account.id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if seller is None:
            raise SellerProfileNotFound
        if seller.status != "ACTIVE":
            raise SellerShopForbidden
        changes = body.model_dump(exclude_unset=True)
        category_id = changes.get("shop_category_id")
        if category_id is not None and category_id != seller.shop_category_id:
            category = session.scalar(select(Category).where(Category.id == category_id).with_for_update())
            if category is None or category.status != "ACTIVE":
                raise ShopCategoryUnavailable
        for field, value in changes.items():
            setattr(seller, field, value)
        seller.updated_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(seller)
    return seller


def get_latest_rejection_reason(session: Session, seller_id: UUID) -> str | None:
    return session.scalar(
        select(SellerStatusHistory.reason)
        .where(
            SellerStatusHistory.seller_id == seller_id,
            SellerStatusHistory.action == "APPLICATION_REJECTED",
        )
        .order_by(SellerStatusHistory.created_at.desc(), SellerStatusHistory.id.desc())
        .limit(1)
    )


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
