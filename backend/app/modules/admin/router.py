"""Admin endpoints for reviewing submitted seller applications."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.admin import service
from app.modules.admin.schemas import (
    SellerDecision,
    SellerDecisionResponse,
    SellerDetailResponse,
    SellerListResponse,
    SellerRejectionRequest,
    SellerStatusFilter,
)
from app.modules.auth.dependencies import require_active_admin
from app.modules.auth.models import Account

router = APIRouter(prefix="/api/v1/admin/sellers", tags=["admin seller review"])
DbSession = Annotated[Session, Depends(get_db)]
ActiveAdmin = Annotated[Account, Depends(require_active_admin)]


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, service.SellerNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "SELLER_NOT_FOUND"}) from None
    if isinstance(error, service.SellerDecisionConflict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "SELLER_DECISION_CONFLICT"}) from None
    if isinstance(error, service.SellerSelfReviewForbidden):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "SELLER_CANNOT_REVIEW_OWN_APPLICATION"}) from None


@router.get("", response_model=SellerListResponse)
def get_sellers(
    session: DbSession,
    _admin: ActiveAdmin,
    seller_status: Annotated[SellerStatusFilter, Query(alias="status")] = SellerStatusFilter.PENDING,
    page: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SellerListResponse:
    return service.list_sellers(session, seller_status=seller_status, page=page, page_size=page_size)


@router.get("/{seller_id}", response_model=SellerDetailResponse)
def get_seller(seller_id: UUID, session: DbSession, _admin: ActiveAdmin) -> SellerDetailResponse:
    try:
        return service.get_seller_detail(session, seller_id)
    except service.SellerNotFound as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.post("/{seller_id}/approve", response_model=SellerDecisionResponse)
def approve_seller(seller_id: UUID, session: DbSession, admin: ActiveAdmin) -> SellerDecisionResponse:
    try:
        return service.decide_seller(
            session,
            seller_id=seller_id,
            actor=admin,
            decision=SellerDecision.ACTIVE,
        )
    except (service.SellerNotFound, service.SellerDecisionConflict, service.SellerSelfReviewForbidden) as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")


@router.post("/{seller_id}/reject", response_model=SellerDecisionResponse)
def reject_seller(
    seller_id: UUID,
    body: SellerRejectionRequest,
    session: DbSession,
    admin: ActiveAdmin,
) -> SellerDecisionResponse:
    try:
        return service.decide_seller(
            session,
            seller_id=seller_id,
            actor=admin,
            decision=SellerDecision.REJECTED,
            reason=body.reason,
        )
    except (service.SellerNotFound, service.SellerDecisionConflict, service.SellerSelfReviewForbidden) as error:
        _raise_service_error(error)
        raise AssertionError("unreachable")
