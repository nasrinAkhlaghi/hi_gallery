"""Authentication use cases and refresh-token family lifecycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth import repository
from app.modules.auth.models import Account, RefreshToken
from app.modules.auth.schemas import (
    BuyerRegistrationRequest,
    CurrentUserResponse,
    Role,
    SellerRegistrationRequest,
)
from app.modules.auth.security import (
    REFRESH_TOKEN_SECONDS,
    create_access_token,
    dummy_password_hash,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    password_hash_needs_rehash,
    verify_password,
)
from app.modules.buyer.models import Buyer
from app.modules.seller.models import Seller, SellerStatusHistory

logger = logging.getLogger(__name__)


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class ConcurrentRefreshError(Exception):
    pass


@dataclass(frozen=True)
class AuthSession:
    user: CurrentUserResponse
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class RefreshOutcome:
    session: AuthSession | None = None
    error: str | None = None


def current_user_response(account: Account) -> CurrentUserResponse:
    roles = repository.account_roles(account)
    return CurrentUserResponse(
        id=account.id,
        email=account.email,
        roles=sorted(roles, key=lambda role: role.value),
        seller_status=account.seller.status if account.seller is not None else None,
    )


def _create_account_profile(session: Session, email: str, password: str, profile: Buyer | Seller) -> CurrentUserResponse:
    now = datetime.now(timezone.utc)
    account = Account(
        id=uuid4(), email=email, password_hash=hash_password(password), status="ACTIVE", created_at=now, updated_at=now
    )
    profile.id = uuid4()
    profile.created_at = now
    profile.updated_at = now
    profile.account = account
    session.add(account)
    if isinstance(profile, Seller):
        session.add(
            SellerStatusHistory(
                seller_id=profile.id,
                previous_status=None,
                new_status=profile.status,
                actor_account_id=account.id,
                actor_type="SELLER",
                action="SELLER_REGISTERED",
                created_at=now,
            )
        )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateEmailError from exc
    session.refresh(account)
    return current_user_response(account)


def register_buyer(session: Session, request: BuyerRegistrationRequest) -> CurrentUserResponse:
    if repository.get_account_by_email(session, str(request.email)) is not None:
        raise DuplicateEmailError
    buyer = Buyer(display_name=request.display_name)
    return _create_account_profile(session, str(request.email), request.password, buyer)


def register_seller(session: Session, request: SellerRegistrationRequest) -> CurrentUserResponse:
    if repository.get_account_by_email(session, str(request.email)) is not None:
        raise DuplicateEmailError
    seller = Seller(shop_name=request.shop_name, description=request.description, status="DRAFT")
    return _create_account_profile(session, str(request.email), request.password, seller)


def authenticate(session: Session, email: str, password: str) -> Account:
    account = repository.get_account_by_email(session, email)
    password_hash = account.password_hash if account is not None else dummy_password_hash()
    password_matches = verify_password(password_hash, password)
    if not account or not password_matches or account.status != "ACTIVE":
        raise InvalidCredentialsError
    if password_hash_needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)
        session.commit()
    return account


def _new_refresh_record(account_id: UUID, family_id: UUID, refresh_token: str, now: datetime) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        account_id=account_id,
        token_hash=hash_refresh_token(refresh_token),
        family_id=family_id,
        created_at=now,
        expires_at=now + timedelta(seconds=REFRESH_TOKEN_SECONDS),
    )


def create_session(session: Session, account: Account) -> AuthSession:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    family_id = uuid4()
    refresh_token = generate_refresh_token()
    session.add(_new_refresh_record(account.id, family_id, refresh_token, now))
    session.commit()
    return AuthSession(
        user=current_user_response(account),
        access_token=create_access_token(account.id, family_id, settings),
        refresh_token=refresh_token,
    )


def _is_postgres_lock_conflict(error: OperationalError) -> bool:
    original = error.orig
    return getattr(original, "sqlstate", None) == "55P03" or getattr(original, "pgcode", None) == "55P03"


def refresh_session(session: Session, raw_refresh_token: str | None) -> RefreshOutcome:
    if not raw_refresh_token:
        return RefreshOutcome(error="invalid")

    settings = get_settings()
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(timezone.utc)
    outcome: RefreshOutcome

    try:
        with session.begin():
            token_record = repository.lock_refresh_token_by_hash(session, token_hash)
            if token_record is None:
                return RefreshOutcome(error="invalid")

            if token_record.revoked_at is not None:
                if token_record.replacement_token_id is None:
                    return RefreshOutcome(error="invalid")
                session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.family_id == token_record.family_id)
                    .values(revoked_at=func.coalesce(RefreshToken.revoked_at, now))
                )
                token_record.reuse_detected_at = now
                logger.warning("refresh_token_reuse_detected family_id=%s", token_record.family_id)
                outcome = RefreshOutcome(error="reused")
            elif token_record.expires_at.replace(tzinfo=token_record.expires_at.tzinfo or timezone.utc) <= now:
                token_record.revoked_at = now
                outcome = RefreshOutcome(error="invalid")
            else:
                account = repository.get_account_by_id(session, token_record.account_id)
                if account is None or account.status != "ACTIVE":
                    token_record.revoked_at = now
                    outcome = RefreshOutcome(error="invalid")
                else:
                    replacement_value = generate_refresh_token()
                    replacement = _new_refresh_record(
                        account.id, token_record.family_id, replacement_value, now
                    )
                    session.add(replacement)
                    session.flush()
                    token_record.revoked_at = now
                    token_record.replacement_token_id = replacement.id
                    outcome = RefreshOutcome(
                        session=AuthSession(
                            user=current_user_response(account),
                            access_token=create_access_token(account.id, token_record.family_id, settings),
                            refresh_token=replacement_value,
                        )
                    )
    except OperationalError as exc:
        if _is_postgres_lock_conflict(exc):
            session.rollback()
            raise ConcurrentRefreshError from exc
        raise

    return outcome


def logout_session(session: Session, raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(timezone.utc)
    with session.begin():
        token_record = session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        if token_record is None:
            return
        if token_record.replacement_token_id is not None:
            session.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == token_record.family_id)
                .values(revoked_at=func.coalesce(RefreshToken.revoked_at, now))
            )
        elif token_record.revoked_at is None:
            token_record.revoked_at = now
