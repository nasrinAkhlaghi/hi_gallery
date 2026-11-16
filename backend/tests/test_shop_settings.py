"""Shop settings contracts against isolated persistence and real auth/CSRF dependencies."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Account, Buyer, Category, Product, Seller, SellerStatusHistory
from app.db.session import Base, get_db
from app.main import app
from app.modules.auth.dependencies import ACCESS_COOKIE
from app.modules.auth.security import create_access_token
from app.modules.seller import service
from app.modules.seller.schemas import SellerShopUpdate

SHOP = "/api/v1/seller/shop"


@pytest.fixture
def shop_client():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        for column in table.columns:
            column.server_default = None
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    account_id, seller_id, other_id, category_id, product_id = [uuid4() for _ in range(5)]
    with sessions.begin() as session:
        for identity in (account_id, other_id):
            session.add(Account(id=identity, email=f"{identity}@example.com", password_hash="unused",
                                status="ACTIVE", created_at=now, updated_at=now))
        session.add(Category(id=category_id, name="Textiles", slug="textiles", status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        for identity, owner in ((seller_id, account_id), (other_id, other_id)):
            session.add(Seller(id=identity, account_id=owner, shop_name="Original Shop", status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        session.add(Product(id=product_id, seller_id=seller_id, category_id=category_id, name="Scarf",
                            price="10.50", stock=2, status="ACTIVE", created_at=now, updated_at=now))

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.cookies.set(ACCESS_COOKIE, create_access_token(account_id, uuid4(), get_settings()), path="/api/v1")
            headers = {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}
            yield client, sessions, headers, account_id, seller_id, other_id, category_id, product_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_settings_save_reload_and_ownership_leave_status_products_and_history_unchanged(shop_client):
    client, sessions, headers, _, seller_id, other_id, category_id, product_id = shop_client
    before = client.get(SHOP).json()
    assert before["theme_id"] == "gallery" and before["shop_category_id"] is None
    assert set(before) == {"id", "shop_name", "description", "logo_url", "shop_category_id", "theme_id", "updated_at"}
    response = client.patch(SHOP, headers=headers, json={
        "shop_name": "  New Shop  ", "description": "  Woven by hand  ",
        "logo_url": "https://example.com/logo.png", "shop_category_id": str(category_id), "theme_id": "clay",
    })
    assert response.status_code == 200, response.text
    assert response.json()["shop_name"] == "New Shop"
    assert response.json()["description"] == "Woven by hand"
    assert client.get(SHOP).json() == response.json()
    with sessions() as session:
        assert session.get(Seller, seller_id).status == "ACTIVE"
        other = session.get(Seller, other_id)
        assert (other.shop_name, other.theme_id, other.shop_category_id) == ("Original Shop", "gallery", None)
        product = session.get(Product, product_id)
        assert (product.category_id, str(product.price), product.stock, product.status) == (category_id, "10.50", 2, "ACTIVE")
        assert session.scalar(select(SellerStatusHistory.id)) is None
    # Approved presentation editing does not relax the onboarding endpoint.
    assert client.patch("/api/v1/seller/profile", headers=headers, json={"shop_name": "No"}).status_code == 409


def test_category_changes_are_independent_and_nullable_fields_can_be_cleared(shop_client):
    client, sessions, headers, _, seller_id, _, category_id, product_id = shop_client
    assert client.patch(SHOP, headers=headers, json={"shop_category_id": str(category_id)}).status_code == 200
    with sessions.begin() as session:
        session.get(Category, category_id).status = "INACTIVE"
    # A previously selected disabled category can remain, including when explicitly sent.
    response = client.patch(SHOP, headers=headers, json={"theme_id": "linen", "shop_category_id": str(category_id)})
    assert response.status_code == 200
    assert client.patch(SHOP, headers=headers, json={"description": "text", "logo_url": "https://example.com/a"}).status_code == 200
    cleared = client.patch(SHOP, headers=headers, json={"shop_category_id": None, "description": None, "logo_url": None})
    assert cleared.status_code == 200
    assert all(cleared.json()[key] is None for key in ("shop_category_id", "description", "logo_url"))
    rejected = client.patch(SHOP, headers=headers, json={"shop_category_id": str(category_id), "shop_name": "Should not save"})
    assert rejected.status_code == 422 and rejected.json()["code"] == "CATEGORY_UNAVAILABLE"
    with sessions() as session:
        assert session.get(Seller, seller_id).shop_name == "Original Shop"
        assert session.get(Product, product_id).category_id == category_id


@pytest.mark.parametrize("body,code", [
    ({"theme_id": "custom"}, "INVALID_SHOP_THEME"),
    ({"theme_id": None}, "INVALID_SHOP_THEME"),
    ({"theme_id": 42}, "INVALID_SHOP_THEME"),
    ({"theme_id": {"css": "x"}}, "INVALID_SHOP_THEME"),
    ({"shop_name": None}, "VALIDATION_ERROR"),
    ({"shop_name": " "}, "VALIDATION_ERROR"),
    ({"shop_name": "x" * 151}, "VALIDATION_ERROR"),
    ({"description": "x" * 10001}, "VALIDATION_ERROR"),
    ({"logo_url": "javascript:alert(1)"}, "VALIDATION_ERROR"),
    ({"logo_url": "https://user:pass@example.com/a"}, "VALIDATION_ERROR"),
    ({"shop_category_id": "invalid"}, "VALIDATION_ERROR"),
    ({"shop_category_id": str(uuid4())}, "CATEGORY_UNAVAILABLE"),
    ({"status": "PENDING"}, "VALIDATION_ERROR"),
    ({"seller_id": str(uuid4())}, "VALIDATION_ERROR"),
    ({"account_id": str(uuid4())}, "VALIDATION_ERROR"),
    ({}, "VALIDATION_ERROR"),
])
def test_invalid_changes_are_rejected_atomically(shop_client, body, code):
    client, _, headers, *_ = shop_client
    before = client.get(SHOP).json()
    payload = {"description": "Must not save", **body} if body else body
    response = client.patch(SHOP, headers=headers, json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == code
    assert client.get(SHOP).json() == before


@pytest.mark.parametrize("seller_status", ["DRAFT", "PENDING", "REJECTED", "SUSPENDED"])
def test_non_active_sellers_cannot_read_or_write_shop_settings(shop_client, seller_status):
    client, sessions, headers, _, seller_id, *_ = shop_client
    with sessions.begin() as session:
        session.get(Seller, seller_id).status = seller_status
    assert client.get(SHOP).status_code == 403
    assert client.patch(SHOP, headers=headers, json={"theme_id": "clay"}).status_code == 403


def test_csrf_origin_authentication_and_role_checks(shop_client):
    client, sessions, headers, account_id, _, *_ = shop_client
    assert client.patch(SHOP, json={"theme_id": "clay"}).status_code == 403
    assert client.patch(SHOP, headers={**headers, "Origin": "https://untrusted.invalid"}, json={"theme_id": "clay"}).status_code == 403
    with sessions.begin() as session:
        session.get(Account, account_id).status = "SUSPENDED"
    assert client.get(SHOP).status_code == 401
    assert client.patch(SHOP, headers=headers, json={"theme_id": "clay"}).status_code == 401
    client.cookies.clear()
    assert client.get(SHOP).status_code == 401
    assert client.patch(SHOP, json={"theme_id": "clay"}).status_code == 401
    buyer_id = uuid4()
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        session.add(Account(id=buyer_id, email="buyer@example.com", password_hash="unused", status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        session.add(Buyer(id=uuid4(), account_id=buyer_id, display_name="Buyer", created_at=now, updated_at=now))
    client.cookies.set(ACCESS_COOKIE, create_access_token(buyer_id, uuid4(), get_settings()), path="/api/v1")
    headers = {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}
    assert client.get(SHOP).status_code == 403
    assert client.patch(SHOP, headers=headers, json={"theme_id": "clay"}).status_code == 403


def test_commit_failure_rolls_back_all_settings(shop_client, monkeypatch):
    _, sessions, _, account_id, seller_id, _, category_id, _ = shop_client
    with sessions() as session:
        account = session.get(Account, account_id)
        def fail_commit():
            session.flush()
            raise RuntimeError("simulated failure after flush")
        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated failure"):
            service.update_seller_shop(session, account, SellerShopUpdate(shop_name="Not saved", theme_id="linen", shop_category_id=category_id))
    with sessions() as session:
        seller = session.get(Seller, seller_id)
        assert (seller.shop_name, seller.theme_id, seller.shop_category_id) == ("Original Shop", "gallery", None)
