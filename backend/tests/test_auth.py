from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Account, RefreshToken, Seller, SellerStatusHistory
from app.db.session import Base, get_db
from app.main import app
from app.modules.auth.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, require_roles
from app.modules.auth.schemas import Role
from app.modules.auth.security import (
    ACCESS_TOKEN_SECONDS,
    REFRESH_TOKEN_SECONDS,
    InvalidAccessToken,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

AUTH = "/api/v1/auth"


@pytest.fixture
def auth_client():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(test_metadata)
    for table in test_metadata.tables.values():
        for column in table.columns:
            column.server_default = None
    test_metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, test_sessions
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_metadata.drop_all(engine)
        engine.dispose()


def csrf(client: TestClient) -> str:
    return client.get(f"{AUTH}/csrf").json()["csrf_token"]


def register_buyer(client: TestClient, *, email: str = "buyer@example.com"):
    token = csrf(client)
    return client.post(
        f"{AUTH}/register",
        json={"email": email, "password": "correct-horse-12", "display_name": "Buyer One"},
        headers={"X-CSRF-Token": token},
    )


def login(client: TestClient, *, email: str = "buyer@example.com", password: str = "correct-horse-12") -> str:
    token = csrf(client)
    response = client.post(
        f"{AUTH}/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    csrf(client)
    return response.json()["id"]


def refresh_cookie(client: TestClient) -> str:
    value = client.cookies.get(REFRESH_COOKIE)
    assert value
    return value


def test_buyer_registration_normalizes_email_and_never_returns_hash_or_tokens(auth_client) -> None:
    client, sessions = auth_client
    response = register_buyer(client, email="  BUYER@Example.COM ")

    assert response.status_code == 201
    assert response.json()["email"] == "buyer@example.com"
    assert response.json()["roles"] == ["BUYER"]
    assert response.json()["seller_status"] is None
    assert "password_hash" not in response.json()
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    with sessions() as session:
        account = session.scalar(select(Account).where(Account.email == "buyer@example.com"))
        assert account is not None
        assert account.password_hash.startswith("$argon2id$")
        assert account.password_hash != "correct-horse-12"
        assert account.buyer is not None
        assert account.seller is None
        assert account.admin is None


def test_seller_registration_creates_only_draft_seller_with_audit_and_rejects_role_assignment(auth_client) -> None:
    client, sessions = auth_client
    token = csrf(client)
    response = client.post(
        f"{AUTH}/register/seller",
        json={
            "email": "seller@example.com",
            "password": "correct-horse-12",
            "shop_name": "Clay Studio",
            "role": "ADMIN",
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "input" not in str(response.json())

    response = client.post(
        f"{AUTH}/register/seller",
        json={"email": "seller@example.com", "password": "correct-horse-12", "shop_name": "Clay Studio"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["SELLER"]
    assert response.json()["seller_status"] == "DRAFT"
    with sessions() as session:
        seller = session.scalar(select(Seller))
        assert seller is not None and seller.status == "DRAFT"
        assert seller.account.buyer is None and seller.account.admin is None
        history = session.scalars(select(SellerStatusHistory).where(SellerStatusHistory.seller_id == seller.id)).all()
        assert len(history) == 1
        assert history[0].previous_status is None
        assert history[0].new_status == "DRAFT"
        assert history[0].actor_account_id == seller.account_id
        assert history[0].actor_type == "SELLER"
        assert history[0].action == "SELLER_REGISTERED"


def test_duplicate_email_registration_is_rejected_after_normalization(auth_client) -> None:
    client, sessions = auth_client
    assert register_buyer(client).status_code == 201
    token = csrf(client)
    response = client.post(
        f"{AUTH}/register",
        json={"email": "BUYER@example.com", "password": "correct-horse-12", "display_name": "Again"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "correct-horse-12", "display_name": "A"},
        {"email": "valid@example.com", "password": "short", "display_name": "A"},
        {"email": "valid@example.com", "password": "correct-horse-12", "display_name": "  "},
    ],
)
def test_invalid_registration_input_is_rejected_without_echoing_values(auth_client, body) -> None:
    client, _ = auth_client
    response = client.post(f"{AUTH}/register", json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "correct-horse-12" not in response.text


def test_argon2_password_hash_verifies_and_does_not_expose_plaintext() -> None:
    encoded = hash_password("correct-horse-12")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "correct-horse-12")
    assert not verify_password(encoded, "wrong-password")


def test_login_sets_securely_scoped_http_only_cookies_and_current_user(auth_client) -> None:
    client, sessions = auth_client
    register_buyer(client)
    csrf_value = csrf(client)
    login_response = client.post(
        f"{AUTH}/login",
        json={"email": "buyer@example.com", "password": "correct-horse-12"},
        headers={"X-CSRF-Token": csrf_value},
    )
    assert login_response.status_code == 200
    user_id = login_response.json()["id"]
    access = client.cookies.get(ACCESS_COOKIE)
    raw_refresh = refresh_cookie(client)
    assert access and raw_refresh

    me = client.get(f"{AUTH}/me")
    assert me.status_code == 200
    assert me.headers["cache-control"] == "no-store"
    assert me.json() == {
        "id": user_id,
        "email": "buyer@example.com",
        "roles": ["BUYER"],
        "seller_status": None,
    }
    assert raw_refresh not in me.text
    assert access not in me.text

    cookie_headers = login_response.headers.get_list("set-cookie")
    access_header = next(value for value in cookie_headers if value.startswith(f"{ACCESS_COOKIE}="))
    refresh_header = next(value for value in cookie_headers if value.startswith(f"{REFRESH_COOKIE}="))
    csrf_header = next(value for value in cookie_headers if value.startswith(f"{CSRF_COOKIE}="))
    assert "HttpOnly" in access_header and "Path=/api/v1" in access_header
    assert "Max-Age=900" in access_header and "SameSite=lax" in access_header
    assert "HttpOnly" in refresh_header and f"Path={AUTH}" in refresh_header
    assert f"Max-Age={REFRESH_TOKEN_SECONDS}" in refresh_header and "SameSite=lax" in refresh_header
    assert "HttpOnly" not in csrf_header and "Path=/api/v1" in csrf_header
    assert "Domain=" not in access_header and "Domain=" not in refresh_header

    set_cookie_headers = me.headers.get_list("set-cookie")
    assert not any(ACCESS_COOKIE in value for value in set_cookie_headers)
    with sessions() as session:
        record = session.scalar(select(RefreshToken))
        assert record is not None
        assert record.token_hash == hash_refresh_token(raw_refresh)
        assert raw_refresh != record.token_hash


def test_auth_cookies_are_secure_in_production(monkeypatch) -> None:
    from fastapi import Response

    from app.modules.auth.router import _set_auth_cookies

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    response = Response()
    try:
        _set_auth_cookies(response, "access-value", "refresh-value")
        cookie_headers = response.headers.getlist("set-cookie")
        assert len(cookie_headers) == 2
        assert all("Secure" in value and "HttpOnly" in value for value in cookie_headers)
    finally:
        get_settings.cache_clear()


def test_invalid_login_uses_same_generic_error_for_unknown_and_wrong_password(auth_client) -> None:
    client, _ = auth_client
    register_buyer(client)
    token = csrf(client)
    unknown = client.post(
        f"{AUTH}/login",
        json={"email": "unknown@example.com", "password": "incorrect-password"},
        headers={"X-CSRF-Token": token},
    )
    wrong = client.post(
        f"{AUTH}/login",
        json={"email": "buyer@example.com", "password": "incorrect-password"},
        headers={"X-CSRF-Token": token},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["code"] == wrong.json()["code"]
    assert unknown.json()["message"] == wrong.json()["message"]
    assert unknown.json()["details"] == wrong.json()["details"]
    assert unknown.json()["code"] == "INVALID_CREDENTIALS"


def test_access_jwt_checks_expiration_signature_issuer_audience_and_token_type() -> None:
    settings = get_settings()
    account_id, family_id = uuid4(), uuid4()
    token = create_access_token(account_id, family_id, settings)
    claims = decode_access_token(token, settings)
    assert claims["sub"] == str(account_id)
    assert claims["sid"] == str(family_id)
    assert claims["token_type"] == "access"
    assert int(claims["exp"]) - int(claims["iat"]) == ACCESS_TOKEN_SECONDS

    invalid_tokens = [
        jwt.encode({"sub": str(account_id)}, "wrong-signing-key-which-is-long-enough", algorithm="HS256"),
        jwt.encode(
            {**claims, "iss": "https://attacker.invalid"},
            settings.jwt_signing_key.get_secret_value(),
            algorithm="HS256",
        ),
        jwt.encode(
            {**claims, "aud": "wrong-audience"},
            settings.jwt_signing_key.get_secret_value(),
            algorithm="HS256",
        ),
        jwt.encode(
            {**claims, "token_type": "refresh"},
            settings.jwt_signing_key.get_secret_value(),
            algorithm="HS256",
        ),
        jwt.encode(
            claims,
            settings.jwt_signing_key.get_secret_value(),
            algorithm="HS384",
        ),
        jwt.encode(
            {**claims, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            settings.jwt_signing_key.get_secret_value(),
            algorithm="HS256",
        ),
        "malformed.jwt.token",
    ]
    for invalid in invalid_tokens:
        with pytest.raises(InvalidAccessToken):
            decode_access_token(invalid, settings)


def test_refresh_rotates_opaque_token_and_detected_reuse_revokes_family(auth_client) -> None:
    client, sessions = auth_client
    register_buyer(client)
    login(client)
    previous = refresh_cookie(client)
    csrf_value = client.get(f"{AUTH}/csrf").json()["csrf_token"]
    assert len(previous) >= 60

    rotated = client.post(f"{AUTH}/refresh", headers={"X-CSRF-Token": csrf_value})
    assert rotated.status_code == 200
    successor = refresh_cookie(client)
    assert successor != previous
    with sessions() as session:
        old = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(previous)))
        assert old is not None
        assert old.revoked_at is not None
        assert old.replacement_token_id is not None
        new = session.get(RefreshToken, old.replacement_token_id)
        assert new is not None and new.token_hash == hash_refresh_token(successor)
        assert new.expires_at - new.created_at == timedelta(seconds=REFRESH_TOKEN_SECONDS)

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, previous, domain="testserver.local", path=f"{AUTH}")
    reuse_csrf = client.get(f"{AUTH}/csrf").json()["csrf_token"]
    reused = client.post(f"{AUTH}/refresh", headers={"X-CSRF-Token": reuse_csrf})
    assert reused.status_code == 401
    with sessions() as session:
        family = session.scalars(select(RefreshToken)).all()
        assert len(family) == 2
        assert all(record.revoked_at is not None for record in family)
        assert family[0].reuse_detected_at is not None or family[1].reuse_detected_at is not None


def test_expired_refresh_token_is_rejected_and_revoked(auth_client) -> None:
    client, sessions = auth_client
    register_buyer(client)
    login(client)
    raw = refresh_cookie(client)
    csrf_value = client.get(f"{AUTH}/csrf").json()["csrf_token"]
    with sessions() as session:
        record = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        assert record is not None
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()

    response = client.post(f"{AUTH}/refresh", headers={"X-CSRF-Token": csrf_value})
    assert response.status_code == 401
    with sessions() as session:
        record = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        assert record is not None and record.revoked_at is not None


def test_logout_revokes_current_refresh_and_is_safe_to_repeat(auth_client) -> None:
    client, sessions = auth_client
    register_buyer(client)
    login(client)
    raw = refresh_cookie(client)
    csrf_value = client.get(f"{AUTH}/csrf").json()["csrf_token"]
    response = client.post(f"{AUTH}/logout", headers={"X-CSRF-Token": csrf_value})
    assert response.status_code == 204
    assert any(ACCESS_COOKIE in value and "Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
    with sessions() as session:
        record = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        assert record is not None and record.revoked_at is not None
    repeated = client.post(f"{AUTH}/logout")
    assert repeated.status_code == 204


def test_csrf_requires_signed_double_submit_pair_and_allowed_origin(auth_client) -> None:
    client, _ = auth_client
    payload = {"email": "buyer@example.com", "password": "correct-horse-12", "display_name": "Buyer"}
    missing = client.post(f"{AUTH}/register", json=payload)
    assert missing.status_code == 403
    assert missing.json()["code"] == "CSRF_VALIDATION_FAILED"

    token = csrf(client)
    forged_origin = client.post(
        f"{AUTH}/register",
        json=payload,
        headers={"X-CSRF-Token": token, "Origin": "https://attacker.invalid"},
    )
    assert forged_origin.status_code == 403
    assert forged_origin.json()["code"] == "ORIGIN_NOT_ALLOWED"

    client.cookies.set(CSRF_COOKIE, "forged.signature", domain="testserver", path="/api/v1")
    forged_token = client.post(
        f"{AUTH}/register",
        json=payload,
        headers={"X-CSRF-Token": "forged.signature"},
    )
    assert forged_token.status_code == 403


def test_missing_authentication_returns_401_and_pending_seller_is_denied_active_access(auth_client) -> None:
    client, sessions = auth_client
    assert client.get(f"{AUTH}/me").status_code == 401

    token = csrf(client)
    registration = client.post(
        f"{AUTH}/register/seller",
        json={"email": "seller@example.com", "password": "correct-horse-12", "shop_name": "Clay"},
        headers={"X-CSRF-Token": token},
    )
    assert registration.status_code == 201
    with sessions() as session:
        seller = session.scalar(select(Seller))
        assert seller is not None
        seller.status = "PENDING"
        session.commit()
    login(client, email="seller@example.com")
    access = client.cookies.get(ACCESS_COOKIE)

    role_app = FastAPI()

    @role_app.get("/api/v1/seller/approved-action")
    def approved_seller_action(account: Account = Depends(require_roles(Role.SELLER, active_seller=True))):
        return {"account_id": str(account.id)}

    role_app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    with TestClient(role_app) as role_client:
        denied = role_client.get("/api/v1/seller/approved-action", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "SELLER_NOT_ACTIVE"


@pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None
    or os.getenv("TEST_DATABASE_ISOLATED") != "1"
    or os.getenv("TEST_DATABASE_URL") == os.getenv("DATABASE_URL"),
    reason="requires a separate PostgreSQL database explicitly marked TEST_DATABASE_ISOLATED=1",
)
def test_concurrent_refresh_has_at_most_one_successor(monkeypatch) -> None:
    """PostgreSQL-only locking test; never connects to DATABASE_URL or the shared development DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    from app.modules.auth.service import ConcurrentRefreshError, refresh_session

    schema_name = f"auth_test_{uuid4().hex}"
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_size=4,
        connect_args={"options": f"-c search_path={schema_name}"},
    )
    test_metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(test_metadata)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    test_metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    account_id = uuid4()
    family_id = uuid4()
    now = datetime.now(timezone.utc)
    raw = os.urandom(48).hex()
    with sessions.begin() as session:
        session.add(Account(id=account_id, email=f"race-{account_id}@example.com", password_hash="unused"))
        session.flush()
        session.add(
            RefreshToken(
                id=uuid4(),
                account_id=account_id,
                token_hash=hash_refresh_token(raw),
                family_id=family_id,
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )

    barrier = threading.Barrier(2)

    def attempt_refresh():
        with sessions() as session:
            barrier.wait(timeout=5)
            try:
                return refresh_session(session, raw)
            except ConcurrentRefreshError:
                return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt_refresh(), range(2)))
        successes = [result for result in results if result is not None and result.session is not None]
        assert len(successes) == 1
        with sessions() as session:
            family = session.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
            assert len(family) == 2
            original = next(record for record in family if record.token_hash == hash_refresh_token(raw))
            successor = next(record for record in family if record.id == original.replacement_token_id)
            assert original.revoked_at is not None
            assert successor.account_id == account_id
            assert successor.family_id == family_id

        # A replay after a committed rotation revokes every row in the affected family.
        with sessions() as session:
            replay = refresh_session(session, raw)
            assert replay.error == "reused"
        with sessions() as session:
            family = session.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
            assert all(record.revoked_at is not None for record in family)
            assert any(record.reuse_detected_at is not None for record in family)

        # An exception after the successor is flushed must roll the whole rotation back.
        rollback_account_id = uuid4()
        rollback_family_id = uuid4()
        rollback_raw = os.urandom(48).hex()
        with sessions.begin() as session:
            session.add(
                Account(
                    id=rollback_account_id,
                    email=f"rollback-{rollback_account_id}@example.com",
                    password_hash="unused",
                )
            )
            session.flush()
            session.add(
                RefreshToken(
                    id=uuid4(),
                    account_id=rollback_account_id,
                    token_hash=hash_refresh_token(rollback_raw),
                    family_id=rollback_family_id,
                    created_at=now,
                    expires_at=now + timedelta(days=7),
                )
            )

        import app.modules.auth.service as auth_service

        def fail_access_token_creation(*args, **kwargs):
            raise RuntimeError("injected failure after successor flush")

        monkeypatch.setattr(auth_service, "create_access_token", fail_access_token_creation)
        with sessions() as session, pytest.raises(RuntimeError, match="injected failure"):
            refresh_session(session, rollback_raw)
        with sessions() as session:
            rollback_family = session.scalars(
                select(RefreshToken).where(RefreshToken.family_id == rollback_family_id)
            ).all()
            assert len(rollback_family) == 1
            assert rollback_family[0].revoked_at is None
            assert rollback_family[0].replacement_token_id is None
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()
