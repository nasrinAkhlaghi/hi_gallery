"""Reusable authentication, CSRF and role authorization dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.auth import repository
from app.modules.auth.models import Account
from app.modules.auth.schemas import Role
from app.modules.auth.security import InvalidAccessToken, current_csrf_binding, decode_access_token, valid_csrf_pair

ACCESS_COOKIE = "hi_gallery_access"
REFRESH_COOKIE = "hi_gallery_refresh"
CSRF_COOKIE = "hi_gallery_csrf"
CSRF_HEADER = "X-CSRF-Token"
ACCESS_COOKIE_PATH = "/api/v1"
REFRESH_COOKIE_PATH = "/api/v1/auth"
CSRF_COOKIE_PATH = "/api/v1"


def require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "ORIGIN_NOT_ALLOWED"})


def require_csrf(request: Request, *, binding: str | None = None) -> None:
    require_allowed_origin(request)
    settings = get_settings()
    actual_binding = binding or current_csrf_binding(
        request.cookies.get(REFRESH_COOKIE), request.cookies.get(ACCESS_COOKIE), settings
    )
    if not valid_csrf_pair(
        request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER), actual_binding, settings
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "CSRF_VALIDATION_FAILED"})


def get_current_account(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> Account:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTHENTICATION_REQUIRED"})
    try:
        claims = decode_access_token(token, get_settings())
        account_id = UUID(str(claims["sub"]))
    except (InvalidAccessToken, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_ACCESS_TOKEN"}) from None

    account = repository.get_account_by_id(session, account_id)
    if account is None or account.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_ACCESS_TOKEN"})

    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_csrf(
            request,
            binding=current_csrf_binding(
                request.cookies.get(REFRESH_COOKIE), request.cookies.get(ACCESS_COOKIE), get_settings()
            ),
        )
    return account


def require_roles(*roles: Role, active_seller: bool = False) -> Callable[..., Account]:
    allowed_roles = set(roles)

    def role_dependency(
        account: Annotated[Account, Depends(get_current_account)],
    ) -> Account:
        actual_roles = set(repository.account_roles(account))
        if not allowed_roles.intersection(actual_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "INSUFFICIENT_ROLE"})
        if active_seller and (account.seller is None or account.seller.status != "ACTIVE"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "SELLER_NOT_ACTIVE"})
        return account

    return role_dependency


def require_active_admin(account: Annotated[Account, Depends(get_current_account)]) -> Account:
    """Require an active Admin profile, not merely an Admin relationship."""
    if account.admin is None or account.admin.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "ACTIVE_ADMIN_REQUIRED"})
    return account
