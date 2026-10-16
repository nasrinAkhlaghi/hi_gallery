"""HTTP endpoints for account registration and cookie-based authentication."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import (
    ACCESS_COOKIE,
    ACCESS_COOKIE_PATH,
    CSRF_COOKIE,
    CSRF_COOKIE_PATH,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    get_current_account,
    require_csrf,
)
from app.modules.auth.models import Account
from app.modules.auth.schemas import (
    BuyerRegistrationRequest,
    CsrfTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    SellerRegistrationRequest,
)
from app.modules.auth.security import (
    ACCESS_TOKEN_SECONDS,
    REFRESH_TOKEN_SECONDS,
    current_csrf_binding,
    new_csrf_token,
    verify_csrf_token,
)
from app.modules.auth.service import (
    ConcurrentRefreshError,
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate,
    create_session,
    current_user_response,
    logout_session,
    refresh_session,
    register_buyer,
    register_seller,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db)]


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    common = {"secure": settings.secure_cookies, "samesite": "lax", "domain": None}
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=ACCESS_TOKEN_SECONDS,
        expires=now + timedelta(seconds=ACCESS_TOKEN_SECONDS),
        path=ACCESS_COOKIE_PATH,
        httponly=True,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=REFRESH_TOKEN_SECONDS,
        expires=now + timedelta(seconds=REFRESH_TOKEN_SECONDS),
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    common = {"secure": settings.secure_cookies, "samesite": "lax", "domain": None}
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_COOKIE_PATH, httponly=True, **common)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, **common)
    response.delete_cookie(CSRF_COOKIE, path=CSRF_COOKIE_PATH, httponly=False, **common)


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=REFRESH_TOKEN_SECONDS,
        path=CSRF_COOKIE_PATH,
        httponly=False,
        secure=get_settings().secure_cookies,
        samesite="lax",
    )


@router.get("/csrf", response_model=CsrfTokenResponse)
def csrf_token(request: Request, response: Response) -> CsrfTokenResponse:
    """Return a signed double-submit CSRF value; authentication tokens remain HttpOnly."""
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    binding = current_csrf_binding(
        request.cookies.get(REFRESH_COOKIE), request.cookies.get(ACCESS_COOKIE), settings
    )
    token = request.cookies.get(CSRF_COOKIE)
    if token is None or not verify_csrf_token(token, binding, settings):
        token = new_csrf_token(binding, settings)
    _set_csrf_cookie(response, token)
    return CsrfTokenResponse(csrf_token=token)


@router.post("/register", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: BuyerRegistrationRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    require_csrf(request)
    try:
        return register_buyer(session, body)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail={"code": "EMAIL_ALREADY_REGISTERED"}) from None


@router.post("/register/seller", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
def register_seller_account(
    body: SellerRegistrationRequest,
    request: Request,
    response: Response,
    session: DbSession,
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    require_csrf(request)
    try:
        return register_seller(session, body)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail={"code": "EMAIL_ALREADY_REGISTERED"}) from None


@router.post("/login", response_model=CurrentUserResponse)
def login(body: LoginRequest, request: Request, response: Response, session: DbSession) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    require_csrf(request)
    try:
        account = authenticate(session, str(body.email), body.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS"}) from None
    auth_session = create_session(session, account)
    _set_auth_cookies(response, auth_session.access_token, auth_session.refresh_token)
    csrf_binding = current_csrf_binding(auth_session.refresh_token, auth_session.access_token, get_settings())
    _set_csrf_cookie(response, new_csrf_token(csrf_binding, get_settings()))
    return auth_session.user


@router.post("/refresh", response_model=CurrentUserResponse)
def refresh(request: Request, response: Response, session: DbSession) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    require_csrf(request)
    try:
        outcome = refresh_session(session, request.cookies.get(REFRESH_COOKIE))
    except ConcurrentRefreshError:
        raise HTTPException(
            status_code=409,
            detail={"code": "REFRESH_IN_PROGRESS", "message": "A refresh is already in progress"},
        ) from None
    if outcome.session is None:
        failure = JSONResponse(
            status_code=401,
            content={
                "code": "REFRESH_TOKEN_INVALID",
                "message": "Refresh token is invalid",
                "details": None,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            headers={"Cache-Control": "no-store"},
        )
        _clear_auth_cookies(failure)
        return failure
    _set_auth_cookies(response, outcome.session.access_token, outcome.session.refresh_token)
    csrf_binding = current_csrf_binding(outcome.session.refresh_token, outcome.session.access_token, get_settings())
    _set_csrf_cookie(response, new_csrf_token(csrf_binding, get_settings()))
    return outcome.session.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DbSession) -> Response:
    response.headers["Cache-Control"] = "no-store"
    if request.cookies.get(REFRESH_COOKIE) or request.cookies.get(ACCESS_COOKIE):
        require_csrf(request)
    else:
        from app.modules.auth.dependencies import require_allowed_origin

        require_allowed_origin(request)
    logout_session(session, request.cookies.get(REFRESH_COOKIE))
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    response: Response,
    account: Annotated[Account, Depends(get_current_account)],
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return current_user_response(account)
