"""Seller application review use cases."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.admin.models import Admin
from app.modules.admin.schemas import (
    SellerDecision,
    SellerDecisionResponse,
    SellerDetailResponse,
    SellerHistoryItem,
    SellerListItem,
    SellerListResponse,
    SellerStatusFilter,
)
from app.modules.auth.models import Account
from app.modules.seller.models import Seller, SellerStatusHistory


class SellerNotFound(Exception):
    pass


class SellerDecisionConflict(Exception):
    pass


class SellerSelfReviewForbidden(Exception):
    pass


def list_sellers(
    session: Session,
    *,
    seller_status: SellerStatusFilter,
    page: int,
    page_size: int,
) -> SellerListResponse:
    latest_submissions = (
        select(
            SellerStatusHistory.seller_id.label("seller_id"),
            func.max(SellerStatusHistory.created_at).label("submitted_at"),
        )
        .where(SellerStatusHistory.action == "APPLICATION_SUBMITTED")
        .group_by(SellerStatusHistory.seller_id)
        .subquery()
    )
    total = session.scalar(select(func.count()).select_from(Seller).where(Seller.status == seller_status.value)) or 0
    rows = session.execute(
        select(Seller, latest_submissions.c.submitted_at)
        .outerjoin(latest_submissions, latest_submissions.c.seller_id == Seller.id)
        .where(Seller.status == seller_status.value)
        .order_by(func.coalesce(latest_submissions.c.submitted_at, Seller.created_at).desc(), Seller.id.asc())
        .offset(page * page_size)
        .limit(page_size)
    ).all()
    return SellerListResponse(
        items=[
            SellerListItem(
                seller_id=seller.id,
                shop_name=seller.shop_name,
                seller_status=seller.status,
                created_at=seller.created_at,
                updated_at=seller.updated_at,
                submitted_at=submitted_at,
            )
            for seller, submitted_at in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_seller_detail(session: Session, seller_id: UUID) -> SellerDetailResponse:
    seller = session.get(Seller, seller_id)
    if seller is None:
        raise SellerNotFound

    history_rows = session.execute(
        select(SellerStatusHistory, Admin.display_name)
        .outerjoin(Admin, Admin.account_id == SellerStatusHistory.actor_account_id)
        .where(SellerStatusHistory.seller_id == seller_id)
        .order_by(SellerStatusHistory.created_at.asc(), SellerStatusHistory.id.asc())
    ).all()
    return SellerDetailResponse(
        seller_id=seller.id,
        shop_name=seller.shop_name,
        description=seller.description,
        logo_url=seller.logo_url,
        seller_status=seller.status,
        created_at=seller.created_at,
        updated_at=seller.updated_at,
        history=[
            SellerHistoryItem(
                previous_status=event.previous_status,
                new_status=event.new_status,
                action=event.action,
                timestamp=event.created_at,
                actor_type=event.actor_type,
                actor_name=admin_name if event.actor_type == "ADMIN" else None,
                reason=event.reason,
            )
            for event, admin_name in history_rows
        ],
    )


def decide_seller(
    session: Session,
    *,
    seller_id: UUID,
    actor: Account,
    decision: SellerDecision,
    reason: str | None = None,
) -> SellerDecisionResponse:
    row = session.execute(select(Seller.account_id, Seller.status).where(Seller.id == seller_id)).one_or_none()
    if row is None:
        raise SellerNotFound
    if row.account_id == actor.id:
        raise SellerSelfReviewForbidden
    if row.status != "PENDING":
        raise SellerDecisionConflict

    decided_at = datetime.now(timezone.utc)
    result = session.execute(
        update(Seller)
        .where(Seller.id == seller_id, Seller.status == "PENDING", Seller.account_id != actor.id)
        .values(status=decision.value, updated_at=decided_at)
        .returning(Seller.id)
    ).first()
    if result is None:
        session.rollback()
        latest = session.execute(select(Seller.account_id, Seller.status).where(Seller.id == seller_id)).one_or_none()
        if latest is None:
            raise SellerNotFound
        if latest.account_id == actor.id:
            raise SellerSelfReviewForbidden
        raise SellerDecisionConflict

    session.add(
        SellerStatusHistory(
            seller_id=seller_id,
            previous_status="PENDING",
            new_status=decision.value,
            actor_account_id=actor.id,
            actor_type="ADMIN",
            action="APPLICATION_APPROVED" if decision.value == "ACTIVE" else "APPLICATION_REJECTED",
            reason=reason,
            created_at=decided_at,
        )
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return SellerDecisionResponse(seller_id=seller_id, seller_status=decision, decided_at=decided_at)
