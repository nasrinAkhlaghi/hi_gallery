"""Exercise registration through signed-out discovery using real API dependencies."""

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import MetaData, create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Account, Admin, Category, Product, Seller, SellerStatusHistory
from app.db.session import Base, get_db
from app.main import app
from app.modules.auth.security import hash_password

API = "/api/v1"
PASSWORD = "disposable-flow-password"


@pytest.fixture
def storefront_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "product_upload_dir", tmp_path / "products")
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
    admin_id, product_category, shop_category = uuid4(), uuid4(), uuid4()
    with sessions.begin() as session:
        session.add(Account(id=admin_id, email="flow-admin@example.com", password_hash=hash_password(PASSWORD), status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        session.add(Admin(id=uuid4(), account_id=admin_id, display_name="Test Admin", status="ACTIVE", created_at=now, updated_at=now))
        for category_id, name in ((product_category, "Ceramics"), (shop_category, "Textiles")):
            session.add(Category(id=category_id, name=name, slug=name.lower(), status="ACTIVE", created_at=now, updated_at=now))

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as seller, TestClient(app) as admin, TestClient(app) as visitor:
            yield seller, admin, visitor, sessions, product_category, shop_category
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def csrf(client):
    return {"X-CSRF-Token": client.get(f"{API}/auth/csrf").json()["csrf_token"]}


def test_registration_approval_publication_and_buyer_discovery(storefront_flow):
    seller, admin, visitor, sessions, product_category, shop_category = storefront_flow
    registered = seller.post(f"{API}/auth/register/seller", headers=csrf(seller), json={
        "email": "flow-maker@example.com", "password": PASSWORD, "shop_name": "Flow Studio",
    })
    assert registered.status_code == 201, registered.text
    assert seller.post(f"{API}/auth/login", headers=csrf(seller), json={"email": "flow-maker@example.com", "password": PASSWORD}).status_code == 200
    assert seller.get(f"{API}/seller/shop").status_code == 403
    profile = seller.get(f"{API}/seller/profile").json()
    assert profile["status"] == "DRAFT"
    seller_id = profile["id"]
    assert seller.patch(f"{API}/seller/profile", headers=csrf(seller), json={"description": "Made by hand"}).status_code == 200
    assert seller.post(f"{API}/seller/application/submit", headers=csrf(seller)).status_code == 200
    assert visitor.get(f"{API}/shops/{seller_id}").status_code == 404

    assert admin.post(f"{API}/auth/login", headers=csrf(admin), json={"email": "flow-admin@example.com", "password": PASSWORD}).status_code == 200
    assert admin.get(f"{API}/admin/sellers").json()["items"][0]["seller_id"] == seller_id
    assert admin.post(f"{API}/admin/sellers/{seller_id}/approve", headers=csrf(admin)).status_code == 200
    assert seller.get(f"{API}/auth/me").json()["seller_status"] == "ACTIVE"
    assert seller.patch(f"{API}/seller/shop", headers=csrf(seller), json={"shop_category_id": str(shop_category), "theme_id": "clay"}).status_code == 200

    fields = {"name": "Flow Bowl", "description": "Thrown by hand", "category_id": str(product_category), "price": "19.50", "stock": 3, "status": "DRAFT"}
    created = seller.post(f"{API}/seller/products", headers=csrf(seller), json=fields)
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    data = BytesIO()
    Image.new("RGB", (32, 32), "#b07550").save(data, format="PNG")
    uploaded = seller.post(f"{API}/seller/products/{product_id}/images", headers={**csrf(seller), "Content-Type": "image/png"}, content=data.getvalue())
    assert uploaded.status_code == 201, uploaded.text
    assert visitor.get(f"{API}/shops/{seller_id}/products").json()["total"] == 0
    assert visitor.get(f"{API}/products/{product_id}").status_code == 404

    fields["status"] = "ACTIVE"
    assert seller.put(f"{API}/seller/products/{product_id}", headers=csrf(seller), json=fields).status_code == 200
    for path in (
        f"/products?q=flow&category_id={product_category}",
        f"/shops/{seller_id}/products?category_id={product_category}",
        f"/categories/{product_category}/products",
    ):
        response = visitor.get(API + path)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == product_id
    detail = visitor.get(f"{API}/products/{product_id}").json()
    assert detail["price"] == "19.50"
    assert detail["seller"] == {"id": seller_id, "shop_name": "Flow Studio"}
    assert detail["category"]["id"] == str(product_category)
    assert visitor.get(detail["images"][0]["url"]).status_code == 200
    assert not visitor.cookies  # Public discovery never requires a buyer session.

    for theme in ("gallery", "linen", "clay"):
        assert seller.patch(f"{API}/seller/shop", headers=csrf(seller), json={"theme_id": theme}).status_code == 200
        public_shop = visitor.get(f"{API}/shops/{seller_id}").json()
        assert public_shop["theme_id"] == theme
        assert public_shop["category"]["id"] == str(shop_category)

    fields["status"] = "INACTIVE"
    assert seller.put(f"{API}/seller/products/{product_id}", headers=csrf(seller), json=fields).status_code == 200
    assert visitor.get(f"{API}/products/{product_id}").status_code == 404
    assert visitor.get(f"{API}/products").json()["total"] == 0
    fields.update(status="SOLD_OUT", stock=0)
    assert seller.put(f"{API}/seller/products/{product_id}", headers=csrf(seller), json=fields).status_code == 200
    assert visitor.get(f"{API}/products/{product_id}").json()["status"] == "SOLD_OUT"
    with sessions.begin() as session:
        stored = session.scalar(select(Seller).where(Seller.shop_name == "Flow Studio"))
        assert stored.status == "ACTIVE"
        assert session.scalar(select(Product.category_id).where(Product.seller_id == stored.id)) == product_category
        assert session.scalar(select(func.count()).select_from(SellerStatusHistory).where(SellerStatusHistory.seller_id == stored.id)) == 3
        session.get(Account, stored.account_id).status = "SUSPENDED"
    assert visitor.get(f"{API}/shops/{seller_id}").status_code == 404
    assert visitor.get(f"{API}/products/{product_id}").status_code == 404
    assert visitor.get(f"{API}/products").json()["total"] == 0
