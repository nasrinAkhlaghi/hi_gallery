from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Account, Seller, SellerStatusHistory
from app.db.session import Base, get_db
from app.main import app
from app.modules.auth.dependencies import ACCESS_COOKIE, require_roles
from app.modules.auth.schemas import Role
from app.modules.auth.security import hash_password
from app.modules.seller.service import SellerApplicationConflict, submit_seller_application

AUTH = "/api/v1/auth"
SELLER = "/api/v1/seller"


@pytest.fixture
def onboarding_client():
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
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.pop(get_db, None)
        metadata.drop_all(engine)
        engine.dispose()


def csrf(client: TestClient) -> str:
    return client.get(f"{AUTH}/csrf").json()["csrf_token"]


def register_seller(client: TestClient, email: str = "maker@example.com") -> dict:
    response = client.post(
        f"{AUTH}/register/seller",
        json={"email": email, "password": "correct-horse-12", "shop_name": "Clay Studio"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert response.status_code == 201
    return response.json()


def login_seller(client: TestClient, email: str = "maker@example.com") -> None:
    response = client.post(
        f"{AUTH}/login",
        json={"email": email, "password": "correct-horse-12"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert response.status_code == 200


def test_profile_read_update_and_application_submission_are_owner_scoped(onboarding_client) -> None:
    client, sessions = onboarding_client
    account = register_seller(client)
    login_seller(client)

    profile = client.get(f"{SELLER}/profile")
    assert profile.status_code == 200
    assert profile.json()["shop_name"] == "Clay Studio"
    assert profile.json()["status"] == "DRAFT"
    app_status = client.get(f"{SELLER}/application")
    assert app_status.json() == {"status": "DRAFT", "can_edit": True, "can_submit": True, "rejection_reason": None}

    updated = client.patch(
        f"{SELLER}/profile",
        json={"shop_name": "  New Clay Studio ", "description": "  Handmade pottery  ", "logo_url": "https://example.com/logo.png"},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["shop_name"] == "New Clay Studio"
    assert updated.json()["description"] == "Handmade pottery"
    assert updated.json()["status"] == "DRAFT"

    submitted = client.post(
        f"{SELLER}/application/submit", headers={"X-CSRF-Token": csrf(client)}
    )
    assert submitted.status_code == 200
    assert submitted.json() == {"status": "PENDING", "can_edit": False, "can_submit": False, "rejection_reason": None}
    assert client.get(f"{SELLER}/application").json()["status"] == "PENDING"
    assert client.patch(
        f"{SELLER}/profile",
        json={"shop_name": "Changed after submission"},
        headers={"X-CSRF-Token": csrf(client)},
    ).status_code == 409

    with sessions() as session:
        seller = session.scalar(select(Seller).where(Seller.account_id == UUID(account["id"])))
        assert seller is not None and seller.status == "PENDING"
        history = session.scalars(
            select(SellerStatusHistory).where(SellerStatusHistory.seller_id == seller.id).order_by(SellerStatusHistory.created_at)
        ).all()
        assert [(event.previous_status, event.new_status, event.action) for event in history] == [
            (None, "DRAFT", "SELLER_REGISTERED"),
            ("DRAFT", "PENDING", "APPLICATION_SUBMITTED"),
        ]
        assert all(event.actor_account_id == seller.account_id and event.actor_type == "SELLER" for event in history)


def test_profile_reads_are_scoped_to_the_authenticated_seller(onboarding_client) -> None:
    client, sessions = onboarding_client
    first = register_seller(client, "first@example.com")
    register_seller(client, "second@example.com")
    login_seller(client, "first@example.com")
    profile = client.get(f"{SELLER}/profile")
    assert profile.status_code == 200
    with sessions() as session:
        sellers = session.scalars(select(Seller).order_by(Seller.created_at, Seller.id)).all()
        assert len(sellers) == 2
        first_seller = session.scalar(select(Seller).where(Seller.account_id == UUID(first["id"])))
        assert first_seller is not None
        assert profile.json()["id"] == str(first_seller.id)
        assert profile.json()["id"] != str(next(seller for seller in sellers if seller.id != first_seller.id).id)


@pytest.mark.parametrize(
    "body",
    [
        {"shop_name": "  "},
        {"logo_url": "javascript:alert(1)"},
        {"status": "ACTIVE"},
        {"account_id": str(uuid4())},
        {"reviewer_id": str(uuid4())},
        {"audit": []},
        {},
    ],
)
def test_profile_update_validation_rejects_invalid_and_mass_assigned_fields(onboarding_client, body) -> None:
    client, _ = onboarding_client
    register_seller(client)
    login_seller(client)
    response = client.patch(
        f"{SELLER}/profile", json=body, headers={"X-CSRF-Token": csrf(client)}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_seller_endpoints_require_authentication_role_and_csrf(onboarding_client) -> None:
    client, _ = onboarding_client
    assert client.get(f"{SELLER}/profile").status_code == 401
    register_seller(client)
    login_seller(client)
    missing_csrf = client.post(f"{SELLER}/application/submit")
    assert missing_csrf.status_code == 403


def test_duplicate_submission_conflicts_and_does_not_add_an_audit_event(onboarding_client) -> None:
    client, sessions = onboarding_client
    register_seller(client)
    login_seller(client)
    headers = {"X-CSRF-Token": csrf(client)}
    submitted = client.post(f"{SELLER}/application/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    duplicate = client.post(f"{SELLER}/application/submit", headers={"X-CSRF-Token": csrf(client)})
    assert duplicate.status_code == 409
    with sessions() as session:
        assert session.query(SellerStatusHistory).count() == 2


def test_submission_rolls_back_status_and_history_together(onboarding_client, monkeypatch) -> None:
    client, sessions = onboarding_client
    user = register_seller(client)
    with sessions() as session:
        account = session.get(Account, UUID(user["id"]))
        assert account is not None

        def fail_commit():
            raise RuntimeError("simulated commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            submit_seller_application(session, account)
        session.rollback()

    with sessions() as session:
        seller = session.scalar(select(Seller).where(Seller.account_id == UUID(user["id"])))
        assert seller is not None and seller.status == "DRAFT"
        assert session.query(SellerStatusHistory).count() == 1


def test_restricted_seller_cannot_edit_or_submit(onboarding_client) -> None:
    client, sessions = onboarding_client
    register_seller(client)
    login_seller(client)
    with sessions() as session:
        seller = session.scalar(select(Seller))
        assert seller is not None
        seller.status = "SUSPENDED"
        session.commit()
    headers = {"X-CSRF-Token": csrf(client)}
    assert client.patch(f"{SELLER}/profile", json={"shop_name": "Blocked"}, headers=headers).status_code == 403
    assert client.post(f"{SELLER}/application/submit", headers={"X-CSRF-Token": csrf(client)}).status_code == 403


@pytest.mark.parametrize(("seller_status", "expected_status"), [("DRAFT", 403), ("ACTIVE", 200)])
def test_active_seller_dependency_denies_drafts_and_allows_active_sellers(onboarding_client, seller_status, expected_status) -> None:
    client, sessions = onboarding_client
    register_seller(client)
    with sessions() as session:
        seller = session.scalar(select(Seller))
        assert seller is not None
        seller.status = seller_status
        session.commit()
    login_seller(client)
    access = client.cookies.get(ACCESS_COOKIE)

    role_app = FastAPI()

    @role_app.get("/api/v1/seller/approved-action")
    def approved_seller_action(account: Account = Depends(require_roles(Role.SELLER, active_seller=True))):
        return {"account_id": str(account.id)}

    role_app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    with TestClient(role_app) as role_client:
        response = role_client.get("/api/v1/seller/approved-action", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})
    assert response.status_code == expected_status


@pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None
    or os.getenv("TEST_DATABASE_ISOLATED") != "1"
    or os.getenv("TEST_DATABASE_URL") == os.getenv("DATABASE_URL"),
    reason="requires a separate PostgreSQL database explicitly marked TEST_DATABASE_ISOLATED=1",
)
def test_concurrent_submission_creates_one_pending_transition_and_audit_row() -> None:
    """PostgreSQL row-lock test; creates and drops only a private test schema."""
    from app.modules.seller.service import submit_seller_application

    schema_name = f"seller_test_{uuid4().hex}"
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_size=4,
        connect_args={"options": f"-c search_path={schema_name}"},
    )
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    account_id, seller_id = uuid4(), uuid4()
    with sessions.begin() as session:
        account = Account(id=account_id, email=f"{account_id}@example.com", password_hash=hash_password("unused-test-password"))
        seller = Seller(id=seller_id, account_id=account_id, shop_name="Clay", status="DRAFT")
        session.add_all([account, seller])
        session.flush()
        session.add(
            SellerStatusHistory(
                seller_id=seller_id, actor_account_id=account_id, actor_type="SELLER",
                new_status="DRAFT", action="SELLER_REGISTERED"
            )
        )

    barrier = threading.Barrier(2)

    def submit():
        with sessions() as session:
            account = session.get(Account, account_id)
            assert account is not None
            barrier.wait(timeout=5)
            try:
                submit_seller_application(session, account)
                return "submitted"
            except SellerApplicationConflict:
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        assert sorted(results) == ["conflict", "submitted"]
        with sessions() as session:
            seller = session.get(Seller, seller_id)
            assert seller is not None and seller.status == "PENDING"
            events = session.scalars(
                select(SellerStatusHistory).where(SellerStatusHistory.seller_id == seller_id)
            ).all()
            assert len(events) == 2
            assert sum(event.action == "APPLICATION_SUBMITTED" for event in events) == 1
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()


@pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None
    or os.getenv("TEST_DATABASE_ISOLATED") != "1"
    or os.getenv("TEST_DATABASE_URL") == os.getenv("DATABASE_URL"),
    reason="requires a separate PostgreSQL database explicitly marked TEST_DATABASE_ISOLATED=1",
)
def test_migration_preserves_existing_pending_sellers() -> None:
    """Run real Alembic upgrades in a private schema in the dedicated test database."""
    database_url = os.environ["TEST_DATABASE_URL"]
    schema_name = f"migration_test_{uuid4().hex}"
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    old_pgoptions = os.environ.get("PGOPTIONS")
    old_database_url = os.environ.get("DATABASE_URL")
    os.environ["PGOPTIONS"] = f"-c search_path={schema_name}"
    os.environ["DATABASE_URL"] = database_url
    admin_engine.dispose()
    admin_engine = create_engine(database_url, connect_args={"options": f"-c search_path={schema_name}"})
    get_settings.cache_clear()
    repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    config = Config(os.path.join(repository_root, "backend", "alembic.ini"))
    try:
        command.upgrade(config, "0001_initial_schema")
        with admin_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO account (id, email, password_hash) "
                    "VALUES (gen_random_uuid(), 'legacy@example.com', 'unused')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO seller (account_id, shop_name, status) "
                    "SELECT id, 'Legacy Shop', 'PENDING' FROM account WHERE email='legacy@example.com'"
                )
            )
        command.upgrade(config, "head")
        with admin_engine.connect() as connection:
            status_value = connection.scalar(
                text("SELECT status FROM seller WHERE shop_name='Legacy Shop'")
            )
            assert status_value == "PENDING"
    finally:
        if old_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = old_pgoptions
        get_settings.cache_clear()
        if old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database_url
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()
