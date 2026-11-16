"""Seller-owned onboarding, profile and approved-shop settings endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_account, require_roles
from app.modules.auth.models import Account
from app.modules.auth.schemas import Role
from app.modules.seller import service
from app.modules.seller.schemas import (
    SellerApplicationResponse,
    SellerProfileResponse,
    SellerProfileUpdate,
    SellerShopResponse,
    SellerShopUpdate,
    PublicShopResponse,
)

router = APIRouter(prefix="/api/v1/seller", tags=["seller onboarding"])
public_router = APIRouter(prefix="/api/v1/shops", tags=["public shops"])
DbSession = Annotated[Session, Depends(get_db)]
SellerAccount = Annotated[Account, Depends(require_roles(Role.SELLER))]
ActiveSellerAccount = Annotated[Account, Depends(require_roles(Role.SELLER, active_seller=True))]


@public_router.get("/{seller_id}", response_model=PublicShopResponse)
def public_shop(seller_id: UUID, session: DbSession):
    try:
        return service.get_public_shop(session, seller_id)
    except service.SellerProfileNotFound:
        raise HTTPException(404, detail={"code": "SHOP_NOT_FOUND"}) from None


def _profile_or_http_error(action):
    try:
        return action()
    except service.SellerProfileNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "SELLER_PROFILE_NOT_FOUND"}) from None
    except service.SellerOnboardingForbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "SELLER_ONBOARDING_FORBIDDEN"}) from None
    except service.SellerProfileNotEditable:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "SELLER_PROFILE_NOT_EDITABLE"}) from None
    except service.SellerApplicationConflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "INVALID_APPLICATION_TRANSITION"}) from None
    except service.SellerShopForbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "SELLER_NOT_ACTIVE"}) from None
    except service.ShopCategoryUnavailable:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "CATEGORY_UNAVAILABLE"}) from None


@router.get("/shop", response_model=SellerShopResponse)
def get_shop(session: DbSession, account: ActiveSellerAccount):
    return _profile_or_http_error(lambda: service.get_seller_profile(session, account.id))


@router.patch("/shop", response_model=SellerShopResponse)
def patch_shop(body: SellerShopUpdate, session: DbSession, account: ActiveSellerAccount):
    return _profile_or_http_error(lambda: service.update_seller_shop(session, account, body))


@router.get("/profile", response_model=SellerProfileResponse)
def get_profile(session: DbSession, account: SellerAccount) -> SellerProfileResponse:
    return _profile_or_http_error(lambda: service.get_seller_profile(session, account.id))


@router.patch("/profile", response_model=SellerProfileResponse)
def patch_profile(body: SellerProfileUpdate, session: DbSession, account: SellerAccount) -> SellerProfileResponse:
    return _profile_or_http_error(lambda: service.update_seller_profile(session, account, body))


@router.get("/application", response_model=SellerApplicationResponse)
def get_application(session: DbSession, account: SellerAccount) -> SellerApplicationResponse:
    seller = _profile_or_http_error(lambda: service.get_seller_profile(session, account.id))
    can_edit = seller.status == "DRAFT"
    rejection_reason = service.get_latest_rejection_reason(session, seller.id) if seller.status == "REJECTED" else None
    return SellerApplicationResponse(
        status=seller.status,
        can_edit=can_edit,
        can_submit=can_edit,
        rejection_reason=rejection_reason,
    )


@router.post("/application/submit", response_model=SellerApplicationResponse)
def submit_application(session: DbSession, account: SellerAccount) -> SellerApplicationResponse:
    seller = _profile_or_http_error(lambda: service.submit_seller_application(session, account))
    return SellerApplicationResponse(status=seller.status, can_edit=False, can_submit=False)
