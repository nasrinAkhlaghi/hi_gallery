from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import MetaData, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.db.models import Account, RefreshToken
from app.db.session import Base
from app.modules.auth.cleanup_refresh_tokens import cleanup_expired_refresh_tokens


def _sessions() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        for column in table.columns:
            column.server_default = None
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    factory._cleanup_test_metadata = metadata  # type: ignore[attr-defined]
    factory._cleanup_test_engine = engine  # type: ignore[attr-defined]
    return factory


def _insert_token(
    sessions: sessionmaker,
    *,
    account_id,
    family_id,
    now: datetime,
    token_id=None,
    expires_at: datetime,
    replacement_token_id=None,
    revoked_at=None,
) -> RefreshToken:
    token = RefreshToken(
        id=token_id or uuid4(),
        account_id=account_id,
        token_hash=uuid4().hex,
        family_id=family_id,
        created_at=now - timedelta(days=7),
        expires_at=expires_at,
        revoked_at=revoked_at,
        replacement_token_id=replacement_token_id,
    )
    with sessions.begin() as session:
        session.add(token)
    return token


def _dispose(sessions: sessionmaker) -> None:
    sessions._cleanup_test_metadata.drop_all(sessions.kw["bind"])  # type: ignore[attr-defined]
    sessions._cleanup_test_engine.dispose()  # type: ignore[attr-defined]


def test_cleanup_deletes_only_records_past_retention_and_preserves_active_family() -> None:
    sessions = _sessions()
    try:
        now = datetime.now(timezone.utc)
        account_id = uuid4()
        family_id = uuid4()
        with sessions.begin() as session:
            session.add(
                Account(
                    id=account_id,
                    email=f"cleanup-{account_id}@example.com",
                    password_hash="unused",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                )
            )
        old_id = uuid4()
        middle_id = uuid4()
        active_id = uuid4()
        _insert_token(
            sessions,
            account_id=account_id,
            family_id=family_id,
            now=now,
            token_id=active_id,
            expires_at=now + timedelta(days=2),
        )
        _insert_token(
            sessions,
            account_id=account_id,
            family_id=family_id,
            now=now,
            token_id=middle_id,
            expires_at=now - timedelta(days=38),
            replacement_token_id=active_id,
            revoked_at=now - timedelta(days=31),
        )
        _insert_token(
            sessions,
            account_id=account_id,
            family_id=family_id,
            now=now,
            token_id=old_id,
            expires_at=now - timedelta(days=45),
            replacement_token_id=middle_id,
            revoked_at=now - timedelta(days=38),
        )
        recent_id = uuid4()
        _insert_token(
            sessions,
            account_id=account_id,
            family_id=uuid4(),
            now=now,
            token_id=recent_id,
            expires_at=now - timedelta(days=20),
            revoked_at=now - timedelta(days=13),
        )

        result = cleanup_expired_refresh_tokens(sessions, now=now, batch_size=2)

        assert result.eligible_count == 2
        assert result.deleted_count == 2
        assert result.batch_count == 1
        with sessions() as session:
            rows = session.scalars(select(RefreshToken)).all()
            assert {row.id for row in rows} == {active_id, recent_id}
            assert rows[0].family_id == family_id or rows[1].family_id == family_id
    finally:
        _dispose(sessions)


def test_cleanup_dry_run_counts_without_deleting_and_is_repeatable() -> None:
    sessions = _sessions()
    try:
        now = datetime.now(timezone.utc)
        account_id = uuid4()
        with sessions.begin() as session:
            session.add(
                Account(
                    id=account_id,
                    email=f"dry-run-{account_id}@example.com",
                    password_hash="unused",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                )
            )
        ids = [uuid4(), uuid4()]
        for token_id in ids:
            _insert_token(
                sessions,
                account_id=account_id,
                family_id=uuid4(),
                now=now,
                token_id=token_id,
                expires_at=now - timedelta(days=31),
            )

        dry_run = cleanup_expired_refresh_tokens(sessions, dry_run=True, now=now)
        with sessions() as session:
            assert session.scalar(select(RefreshToken.id).limit(1)) is not None
        deleted = cleanup_expired_refresh_tokens(sessions, now=now)
        repeated = cleanup_expired_refresh_tokens(sessions, now=now)

        assert (dry_run.eligible_count, dry_run.deleted_count, dry_run.dry_run) == (2, 0, True)
        assert deleted.deleted_count == 2
        assert repeated.eligible_count == repeated.deleted_count == 0
    finally:
        _dispose(sessions)


def test_cleanup_respects_batch_limit() -> None:
    sessions = _sessions()
    try:
        now = datetime.now(timezone.utc)
        account_id = uuid4()
        with sessions.begin() as session:
            session.add(
                Account(
                    id=account_id,
                    email=f"batches-{account_id}@example.com",
                    password_hash="unused",
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                )
            )
        for _ in range(5):
            _insert_token(
                sessions,
                account_id=account_id,
                family_id=uuid4(),
                now=now,
                expires_at=now - timedelta(days=31),
            )

        result = cleanup_expired_refresh_tokens(sessions, now=now, batch_size=2)

        assert result.deleted_count == 5
        assert result.batch_count == 3
    finally:
        _dispose(sessions)
