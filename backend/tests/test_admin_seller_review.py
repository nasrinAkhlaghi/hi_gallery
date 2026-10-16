from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Account, Admin, Seller, SellerStatusHistory
from app.db.session import Base, get_db
from app.main import app
from app.modules.admin.service import SellerDecisionConflict, decide_seller
from app.modules.admin.schemas import SellerDecision
from app.modules.auth.security import hash_password

AUTH = "/api/v1/auth"
ADMIN = "/api/v1/admin/sellers"
SELLER = "/api/v1/seller"
PASSWORD = "correct-horse-12"


@pytest.fixture
def review_client():
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


def create_admin(sessions, *, email: str = "admin@example.com", status: str = "ACTIVE") -> Account:
    now = datetime.now(timezone.utc)
    account = Account(id=uuid4(), email=email, password_hash=hash_password(PASSWORD), status="ACTIVE", created_at=now, updated_at=now)
    with sessions.begin() as session:
        session.add(account)
        session.flush()
        session.add(Admin(id=uuid4(), account_id=account.id, display_name="Review Admin", status=status, created_at=now, updated_at=now))
        session.flush()
        account_id = account.id
    with sessions() as session:
        return session.get(Account, account_id)


def login(client: TestClient, email: str) -> None:
    response = client.post(
        f"{AUTH}/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-CSRF-Token": csrf(client)},
    )
    assert response.status_code == 200, response.text


def add_seller(sessions, *, shop_name: str, status: str = "PENDING", account: Account | None = None) -> tuple[Account, Seller]:
    now = datetime.now(timezone.utc)
    account = account or Account(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        password_hash=hash_password(PASSWORD),
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    with sessions.begin() as session:
        session.add(account)
        session.flush()
        seller = Seller(
            id=uuid4(),
            account_id=account.id,
            shop_name=shop_name,
            description="Handmade goods",
            logo_url="https://example.com/logo.png",
            status=status,
            created_at=now,
            updated_at=now,
        )
        session.add(seller)
        session.flush()
        if status == "PENDING":
            session.add(
                SellerStatusHistory(
                    seller_id=seller.id,
                    previous_status="DRAFT",
                    new_status="PENDING",
                    actor_account_id=account.id,
                    actor_type="SELLER",
                    action="APPLICATION_SUBMITTED",
                    created_at=now,
                )
            )
        seller_id, account_id = seller.id, account.id
    with sessions() as session:
        return session.get(Account, account_id), session.get(Seller, seller_id)


def admin_login(review_client, *, email="admin@example.com", status="ACTIVE"):
    client, sessions = review_client
    create_admin(sessions, email=email, status=status)
    login(client, email)
    return client, sessions


def test_admin_authentication_requires_an_active_admin_profile(review_client) -> None:
    client, sessions = review_client
    create_admin(sessions, status="INACTIVE")
    _seller_account, seller = add_seller(sessions, shop_name="Pending Shop")
    login(client, "admin@example.com")

    assert client.get(f"{ADMIN}").status_code == 403
    assert client.get(f"{ADMIN}/{seller.id}").status_code == 403
    assert client.post(f"{ADMIN}/{seller.id}/approve", headers={"X-CSRF-Token": csrf(client)}).status_code == 403
    assert client.get(f"{AUTH}/me").json()["roles"] == []


@pytest.mark.parametrize("path", [ADMIN, f"{ADMIN}/00000000-0000-0000-0000-000000000000"])
def test_admin_review_requires_authentication(review_client, path: str) -> None:
    client, _ = review_client
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_buyer_and_seller_cannot_access_admin_review(review_client, role: str) -> None:
    client, _sessions = review_client
    if role == "buyer":
        response = client.post(
            f"{AUTH}/register",
            json={"email": "buyer@example.com", "password": PASSWORD, "display_name": "Buyer"},
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert response.status_code == 201
        email = "buyer@example.com"
    else:
        response = client.post(
            f"{AUTH}/register/seller",
            json={"email": "seller@example.com", "password": PASSWORD, "shop_name": "Seller Shop"},
            headers={"X-CSRF-Token": csrf(client)},
        )
        assert response.status_code == 201
        email = "seller@example.com"
    login(client, email)
    assert client.get(ADMIN).status_code == 403


def test_admin_list_filters_paginates_and_excludes_drafts_by_default(review_client) -> None:
    client, sessions = admin_login(review_client)
    add_seller(sessions, shop_name="First Shop")
    add_seller(sessions, shop_name="Second Shop")
    add_seller(sessions, shop_name="Draft Shop", status="DRAFT")

    default_page = client.get(f"{ADMIN}?page=0&page_size=1")
    assert default_page.status_code == 200
    assert default_page.json()["total"] == 2
    assert len(default_page.json()["items"]) == 1
    assert default_page.json()["items"][0]["seller_status"] == "PENDING"
    second_page = client.get(f"{ADMIN}?page=1&page_size=1")
    assert second_page.json()["items"][0]["seller_id"] != default_page.json()["items"][0]["seller_id"]
    drafts = client.get(f"{ADMIN}?status=DRAFT")
    assert drafts.json()["total"] == 1
    assert drafts.json()["items"][0]["shop_name"] == "Draft Shop"
    assert client.get(f"{ADMIN}?page_size=101").status_code == 422


def test_admin_detail_returns_profile_and_safe_ordered_audit_history(review_client) -> None:
    client, sessions = admin_login(review_client)
    _actor, seller = add_seller(sessions, shop_name="Clay Studio")
    with sessions.begin() as session:
        admin_account = session.scalar(select(Account).where(Account.email == "admin@example.com"))
        session.add(
            SellerStatusHistory(
                seller_id=seller.id,
                previous_status="PENDING",
                new_status="ACTIVE",
                actor_account_id=admin_account.id,
                actor_type="ADMIN",
                action="APPLICATION_APPROVED",
                created_at=datetime.now(timezone.utc),
            )
        )
    response = client.get(f"{ADMIN}/{seller.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["shop_name"] == "Clay Studio"
    assert body["history"][0]["actor_type"] == "SELLER"
    assert body["history"][1]["actor_name"] == "Review Admin"
    assert "email" not in body
    assert "password_hash" not in body
    assert client.patch(f"{ADMIN}/{seller.id}", json={"status": "ACTIVE"}).status_code == 405
    assert client.get(f"{ADMIN}/00000000-0000-0000-0000-000000000000").status_code == 404


def test_admin_approval_is_audited_and_repeated_decision_conflicts(review_client) -> None:
    client, sessions = admin_login(review_client)
    _seller_account, seller = add_seller(sessions, shop_name="Approval Shop")
    approved = client.post(f"{ADMIN}/{seller.id}/approve", headers={"X-CSRF-Token": csrf(client)})
    assert approved.status_code == 200
    assert approved.json()["seller_status"] == "ACTIVE"
    repeated = client.post(f"{ADMIN}/{seller.id}/approve", headers={"X-CSRF-Token": csrf(client)})
    assert repeated.status_code == 409
    with sessions() as session:
        updated = session.get(Seller, seller.id)
        events = session.scalars(
            select(SellerStatusHistory).where(SellerStatusHistory.seller_id == seller.id)
        ).all()
        assert updated.status == "ACTIVE"
        assert sum(event.action == "APPLICATION_APPROVED" for event in events) == 1


def test_rejection_requires_reason_and_is_visible_only_to_owner(review_client) -> None:
    admin_client, sessions = admin_login(review_client)
    seller_account, seller = add_seller(sessions, shop_name="Rejected Shop")
    base = f"{ADMIN}/{seller.id}/reject"
    assert admin_client.post(base, json={}, headers={"X-CSRF-Token": csrf(admin_client)}).status_code == 422
    assert admin_client.post(base, json={"reason": "  "}, headers={"X-CSRF-Token": csrf(admin_client)}).status_code == 422
    rejected = admin_client.post(
        base,
        json={"reason": "  Please add clearer product photographs.  "},
        headers={"X-CSRF-Token": csrf(admin_client)},
    )
    assert rejected.status_code == 200
    assert rejected.json()["seller_status"] == "REJECTED"
    assert admin_client.post(base, json={"reason": "again"}, headers={"X-CSRF-Token": csrf(admin_client)}).status_code == 409

    seller_client = TestClient(app)
    login(seller_client, seller_account.email)
    own_application = seller_client.get(f"{SELLER}/application")
    assert own_application.status_code == 200
    assert own_application.json()["status"] == "REJECTED"
    assert own_application.json()["rejection_reason"] == "Please add clearer product photographs."
    assert "actor_account_id" not in own_application.json()
    other_account, _other_seller = add_seller(sessions, shop_name="Other Seller", status="REJECTED")
    assert other_account.id != seller_account.id
    other_client = TestClient(app)
    login(other_client, other_account.email)
    other_application = other_client.get(f"{SELLER}/application")
    assert other_application.status_code == 200
    assert other_application.json()["rejection_reason"] is None


def test_invalid_transition_and_self_review_are_rejected_without_audit(review_client) -> None:
    client, sessions = admin_login(review_client)
    _account, draft = add_seller(sessions, shop_name="Draft Shop", status="DRAFT")
    assert client.post(f"{ADMIN}/{draft.id}/approve", headers={"X-CSRF-Token": csrf(client)}).status_code == 409

    self_account = Account(id=uuid4(), email="self-admin@example.com", password_hash=hash_password(PASSWORD), status="ACTIVE", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    with sessions.begin() as session:
        session.add(self_account)
        session.flush()
        self_now = datetime.now(timezone.utc)
        session.add(Admin(id=uuid4(), account_id=self_account.id, display_name="Self Admin", status="ACTIVE", created_at=self_now, updated_at=self_now))
        session.add(Seller(id=uuid4(), account_id=self_account.id, shop_name="Own Shop", status="PENDING", created_at=self_now, updated_at=self_now))
        account_id = self_account.id
    login(client, "self-admin@example.com")
    with sessions() as session:
        own_seller = session.scalar(select(Seller).where(Seller.account_id == account_id))
    result = client.post(f"{ADMIN}/{own_seller.id}/approve", headers={"X-CSRF-Token": csrf(client)})
    assert result.status_code == 403
    assert result.json()["code"] == "SELLER_CANNOT_REVIEW_OWN_APPLICATION"


@pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None
    or os.getenv("TEST_DATABASE_ISOLATED") != "1"
    or os.getenv("TEST_DATABASE_URL") == os.getenv("DATABASE_URL"),
    reason="requires a separate PostgreSQL database explicitly marked TEST_DATABASE_ISOLATED=1",
)
def test_concurrent_admin_decisions_allow_exactly_one_and_audit_once() -> None:
    schema_name = f"admin_review_{uuid4().hex}"
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
    actor_id, seller_account_id, seller_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        session.add_all(
            [
                Account(id=actor_id, email="admin@concurrency.test", password_hash="unused", status="ACTIVE"),
                Account(id=seller_account_id, email="seller@concurrency.test", password_hash="unused", status="ACTIVE"),
            ]
        )
        session.add(Admin(id=uuid4(), account_id=actor_id, display_name="Concurrent Admin", status="ACTIVE"))
        session.add(Seller(id=seller_id, account_id=seller_account_id, shop_name="Pending Shop", status="PENDING", created_at=now, updated_at=now))
        session.add(SellerStatusHistory(seller_id=seller_id, previous_status="DRAFT", new_status="PENDING", actor_account_id=seller_account_id, actor_type="SELLER", action="APPLICATION_SUBMITTED", created_at=now))

    barrier = threading.Barrier(2)

    def decide(target_status: str) -> str:
        with sessions() as session:
            actor = session.get(Account, actor_id)
            barrier.wait(timeout=5)
            try:
                decide_seller(session, seller_id=seller_id, actor=actor, decision=SellerDecision(target_status))
                return "success"
            except SellerDecisionConflict:
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(decide, ["ACTIVE", "REJECTED"]))
        assert sorted(outcomes) == ["conflict", "success"]
        with sessions() as session:
            seller = session.get(Seller, seller_id)
            events = session.scalars(select(SellerStatusHistory).where(SellerStatusHistory.seller_id == seller_id)).all()
            decisions = [event for event in events if event.actor_type == "ADMIN"]
            assert seller.status in {"ACTIVE", "REJECTED"}
            assert len(decisions) == 1
            assert decisions[0].new_status == seller.status
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
def test_decision_audit_failure_rolls_back_status_update() -> None:
    schema_name = f"admin_rollback_{uuid4().hex}"
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        connect_args={"options": f"-c search_path={schema_name}"},
    )
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    actor_id, seller_account_id, seller_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        session.add(Account(id=seller_account_id, email="rollback-seller@test", password_hash="unused", status="ACTIVE"))
        session.add(Seller(id=seller_id, account_id=seller_account_id, shop_name="Pending Shop", status="PENDING", created_at=now, updated_at=now))

    try:
        with sessions() as session:
            fake_actor = Account(id=actor_id, email="missing-admin@test", password_hash="unused", status="ACTIVE")
            with pytest.raises(IntegrityError):
                decide_seller(session, seller_id=seller_id, actor=fake_actor, decision=SellerDecision.ACTIVE)
        with sessions() as session:
            assert session.get(Seller, seller_id).status == "PENDING"
            assert session.scalar(select(SellerStatusHistory.id).where(SellerStatusHistory.seller_id == seller_id)) is None
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()
