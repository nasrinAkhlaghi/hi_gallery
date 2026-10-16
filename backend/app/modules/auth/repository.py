"""Database lookups and persistence for accounts and refresh tokens."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.auth.models import Account, RefreshToken
from app.modules.auth.schemas import Role


def get_account_by_email(session: Session, email: str) -> Account | None:
    return session.scalar(
        select(Account)
        .where(Account.email == email)
        .options(joinedload(Account.buyer), joinedload(Account.seller), joinedload(Account.admin))
    )


def get_account_by_id(session: Session, account_id: UUID) -> Account | None:
    return session.scalar(
        select(Account)
        .where(Account.id == account_id)
        .options(joinedload(Account.buyer), joinedload(Account.seller), joinedload(Account.admin))
    )


def get_refresh_token_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def lock_refresh_token_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update(nowait=True)
    )


def revoke_token_family(session: Session, family_id: UUID, revoked_at) -> None:
    session.query(RefreshToken).filter(
        RefreshToken.family_id == family_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: revoked_at}, synchronize_session=False)


def account_roles(account: Account) -> set[Role]:
    roles: set[Role] = set()
    if account.buyer is not None:
        roles.add(Role.BUYER)
    if account.seller is not None:
        roles.add(Role.SELLER)
    if account.admin is not None and account.admin.status == "ACTIVE":
        roles.add(Role.ADMIN)
    return roles
