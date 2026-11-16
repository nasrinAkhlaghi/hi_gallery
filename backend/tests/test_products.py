from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.models import Account, Admin, Buyer, Cart, CartItem, Category, Product, ProductImage, Seller
from app.db.session import Base, get_db
from app.main import app
from app.modules.products import storage
from app.seed_dev import seed

ROOT = "/api/v1/seller/products"
AUTH = "/api/v1/auth"


@pytest.fixture
def products_client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "product_upload_dir", tmp_path / "products")
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        for column in table.columns:
            column.server_default = None
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    now = datetime.now(timezone.utc)
    category_id = uuid4()
    with sessions() as session:
        session.add(Category(id=category_id, name="Ceramics", slug="ceramics", status="ACTIVE", created_at=now, updated_at=now))
        session.commit()
    try:
        with TestClient(app) as client:
            yield client, sessions, category_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def csrf(client):
    return {"X-CSRF-Token": client.get(f"{AUTH}/csrf").json()["csrf_token"]}


def seller_login(client, sessions, email="maker@example.com", status="ACTIVE"):
    result = client.post(f"{AUTH}/register/seller", json={"email": email, "password": "correct-horse-12", "shop_name": "Clay Studio"}, headers=csrf(client))
    assert result.status_code == 201
    with sessions() as session:
        seller = session.scalar(select(Seller).where(Seller.account_id == UUID(result.json()["id"])))
        seller.status = status
        session.commit()
    assert client.post(f"{AUTH}/login", json={"email": email, "password": "correct-horse-12"}, headers=csrf(client)).status_code == 200


def values(default_category_id, **overrides):
    return {"name": "  Clay bowl  ", "description": " Handmade ", "category_id": str(default_category_id), "price": "123.45", "stock": 3, "status": "DRAFT", **overrides}


def create(client, category_id, **overrides):
    response = client.post(ROOT, json=values(category_id, **overrides), headers=csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def png():
    data = BytesIO()
    Image.new("RGB", (12, 12), "red").save(data, format="PNG")
    return data.getvalue()


def test_crud_categories_filter_and_pagination(products_client):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    assert client.get("/api/v1/categories").json()["items"][0]["id"] == str(category_id)
    product = create(client, category_id)
    assert product["name"] == "Clay bowl" and product["price"] == "123.45" and product["images"] == []
    assert "seller_id" not in product
    assert client.get(f"{ROOT}/{product['id']}").json() == product
    published = client.put(f"{ROOT}/{product['id']}", json=values(category_id, price="9999999999.99", stock=0, status="ACTIVE"), headers=csrf(client))
    assert published.status_code == 200 and published.json()["status"] == "ACTIVE"
    create(client, category_id, name="Second bowl")
    page = client.get(f"{ROOT}?page_size=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert client.get(f"{ROOT}?page_size=1&page=1").json()["items"][0]["id"] != page["items"][0]["id"]
    assert client.get(f"{ROOT}?status=ACTIVE").json()["total"] == 1
    assert client.delete(f"{ROOT}/{product['id']}", headers=csrf(client)).status_code == 204
    assert client.get(f"{ROOT}/{product['id']}").status_code == 404


@pytest.mark.parametrize("status", ["DRAFT", "PENDING", "REJECTED", "SUSPENDED"])
def test_non_active_sellers_cannot_use_product_routes(products_client, status):
    client, sessions, category_id = products_client
    seller_login(client, sessions, status=status)
    product_id = uuid4()
    for method, url, extra in [
        ("get", ROOT, {}), ("post", ROOT, {"json": values(category_id)}),
        ("get", f"{ROOT}/{product_id}", {}), ("put", f"{ROOT}/{product_id}", {"json": values(category_id)}),
        ("delete", f"{ROOT}/{product_id}", {}),
        ("post", f"{ROOT}/{product_id}/images", {"content": png()}),
        ("delete", f"{ROOT}/{product_id}/images/{uuid4()}", {}),
    ]:
        response = getattr(client, method)(url, headers=csrf(client), **extra)
        assert response.status_code == 403 and response.json()["code"] == "SELLER_NOT_ACTIVE"


def test_anonymous_buyer_csrf_and_origin_checks(products_client):
    client, sessions, category_id = products_client
    assert client.get(ROOT).status_code == 401
    assert client.post(f"{AUTH}/register", json={"email": "buyer@example.com", "password": "correct-horse-12", "display_name": "Buyer"}, headers=csrf(client)).status_code == 201
    assert client.post(f"{AUTH}/login", json={"email": "buyer@example.com", "password": "correct-horse-12"}, headers=csrf(client)).status_code == 200
    assert client.get(ROOT).status_code == 403
    seller_login(client, sessions)
    assert client.post(ROOT, json=values(category_id)).status_code == 403
    assert client.post(ROOT, json=values(category_id), headers={**csrf(client), "Origin": "https://untrusted.invalid"}).status_code == 403
    assert client.post(ROOT, json=values(category_id), headers=csrf(client)).status_code == 201


def test_foreign_products_and_images_are_hidden_for_every_operation(products_client):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    image = client.post(f"{ROOT}/{product['id']}/images", content=png(), headers={**csrf(client), "Content-Type": "image/png"}).json()
    seller_login(client, sessions, "other@example.com")
    assert client.get(ROOT).json()["total"] == 0
    url = f"{ROOT}/{product['id']}"
    assert client.get(url).status_code == 404
    assert client.put(url, json=values(category_id), headers=csrf(client)).status_code == 404
    assert client.delete(url, headers=csrf(client)).status_code == 404
    assert client.post(url + "/images", content=png(), headers={**csrf(client), "Content-Type": "image/png"}).status_code == 404
    assert client.delete(url + f"/images/{image['id']}", headers=csrf(client)).status_code == 404


@pytest.mark.parametrize("invalid", [
    {"name": "   "}, {"name": "a" * 256}, {"price": "-1"}, {"price": "1.001"}, {"price": "10000000000.00"},
    {"price": "NaN"}, {"price": "Infinity"}, {"stock": -1}, {"stock": 1.5}, {"stock": True}, {"stock": 2147483648},
    {"status": "PENDING"}, {"seller_id": str(uuid4())}, {"category_id": str(uuid4())},
])
def test_invalid_product_fields_are_rejected(products_client, invalid):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    response = client.post(ROOT, json=values(category_id, **invalid), headers=csrf(client))
    assert response.status_code == 422, response.text
    assert client.get(ROOT).json()["total"] == 0


def test_disabled_categories_and_pagination_limits(products_client):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    with sessions() as session:
        session.get(Category, category_id).status = "INACTIVE"
        session.commit()
    assert client.get("/api/v1/categories").json()["total"] == 0
    assert client.post(ROOT, json=values(category_id), headers=csrf(client)).status_code == 422
    assert client.put(f"{ROOT}/{product['id']}", json=values(category_id, name="Updated"), headers=csrf(client)).status_code == 200
    for query in ("page=-1", "page_size=0", "page_size=101", "status=INVALID"):
        assert client.get(f"{ROOT}?{query}").status_code == 422


def test_image_delivery_deletion_and_product_cleanup(products_client):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    url = f"{ROOT}/{product['id']}"
    upload = client.post(url + "/images", content=png(), headers={**csrf(client), "Content-Type": "image/png"})
    assert upload.status_code == 201, upload.text
    image = upload.json()
    assert image["sort_order"] == 0
    assert client.get(image["url"]).status_code == 200
    assert client.get(image["url"]).headers["x-content-type-options"] == "nosniff"
    assert client.get(url).json()["images"] == [image]
    assert client.delete(url + f"/images/{image['id']}", headers=csrf(client)).status_code == 204
    assert client.get(image["url"]).status_code == 404
    assert not list(get_settings().product_upload_dir.iterdir())
    uploaded = client.post(url + "/images", content=png(), headers={**csrf(client), "Content-Type": "image/png"}).json()
    assert client.delete(url, headers=csrf(client)).status_code == 204
    assert client.get(uploaded["url"]).status_code == 404
    assert not list(get_settings().product_upload_dir.iterdir())
    assert client.get("/media/products/not-a-generated-name.png").status_code == 404


def test_invalid_image_content_size_and_commit_failure(products_client, monkeypatch):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    url = f"{ROOT}/{product['id']}/images"
    for content, content_type, expected in [(b"<svg><script/></svg>", "image/svg+xml", 422),
                                             (b"not an image", "image/png", 422), (png(), "image/jpeg", 422),
                                             (b"", "image/png", 422), (b"x" * (storage.MAX_IMAGE_BYTES + 1), "image/png", 413)]:
        assert client.post(url, content=content, headers={**csrf(client), "Content-Type": content_type}).status_code == expected
    from sqlalchemy.orm import Session
    def failed_commit(_):
        raise RuntimeError("simulated write failure")
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", failed_commit)
        with pytest.raises(RuntimeError, match="simulated write failure"):
            client.post(url, content=png(), headers={**csrf(client), "Content-Type": "image/png"})
    assert not list(get_settings().product_upload_dir.iterdir())
    with sessions() as session:
        assert session.scalar(select(ProductImage.id)) is None


def test_referenced_product_cannot_be_deleted(products_client):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    now = datetime.now(timezone.utc)
    with sessions() as session:
        account_id = session.scalar(select(Account.id))
        buyer = Buyer(id=uuid4(), account_id=account_id, display_name="Buyer", created_at=now, updated_at=now)
        session.add(buyer)
        session.flush()
        cart = Cart(id=uuid4(), buyer_id=buyer.id, created_at=now, updated_at=now)
        session.add(cart)
        session.flush()
        session.add(CartItem(id=uuid4(), cart_id=cart.id, product_id=UUID(product["id"]), quantity=1))
        session.commit()
    response = client.delete(f"{ROOT}/{product['id']}", headers=csrf(client))
    assert response.status_code == 409 and response.json()["code"] == "PRODUCT_IN_USE"
    assert client.get(f"{ROOT}/{product['id']}").status_code == 200


def test_seed_is_repeatable_and_never_promotes_existing_accounts(products_client, monkeypatch):
    client, sessions, _ = products_client
    monkeypatch.setattr(get_settings(), "environment", "development")
    with sessions() as session:
        seed(session, "local-admin@example.com", "local-password-12")
        original = session.scalar(select(Account).where(Account.email == "local-admin@example.com")).password_hash
        seed(session, "local-admin@example.com", "different-password-12")
        assert session.scalar(select(Account).where(Account.email == "local-admin@example.com")).password_hash == original
        assert len(session.scalars(select(Category)).all()) == 4
        assert len(session.scalars(select(Admin)).all()) == 1
    seller_login(client, sessions)
    with sessions() as session:
        with pytest.raises(ValueError, match="another or inactive"):
            seed(session, "maker@example.com", "local-password-12")


def test_registration_review_product_and_image_journey(products_client, monkeypatch):
    """Follow the real HTTP route stack without bypassing seller approval."""
    client, sessions, category_id = products_client
    monkeypatch.setattr(get_settings(), "environment", "development")
    with sessions() as session:
        seed(session, "local-admin@example.com", "local-password-12")
    registration = client.post(f"{AUTH}/register/seller", json={"email": "journey@example.com", "password": "correct-horse-12", "shop_name": "Journey Studio"}, headers=csrf(client))
    assert registration.status_code == 201 and registration.json()["seller_status"] == "DRAFT"
    assert client.post(f"{AUTH}/login", json={"email": "journey@example.com", "password": "correct-horse-12"}, headers=csrf(client)).status_code == 200
    profile = client.patch("/api/v1/seller/profile", json={"shop_name": "Handmade Studio", "description": "Local test shop"}, headers=csrf(client))
    assert profile.status_code == 200
    assert client.post("/api/v1/seller/application/submit", headers=csrf(client)).json()["status"] == "PENDING"
    assert client.post(ROOT, json=values(category_id), headers=csrf(client)).status_code == 403
    assert client.post(f"{AUTH}/login", json={"email": "local-admin@example.com", "password": "local-password-12"}, headers=csrf(client)).status_code == 200
    queue = client.get("/api/v1/admin/sellers").json()
    assert queue["items"][0]["seller_id"] == profile.json()["id"]
    approved = client.post(f"/api/v1/admin/sellers/{profile.json()['id']}/approve", headers=csrf(client))
    assert approved.status_code == 200 and approved.json()["seller_status"] == "ACTIVE"
    assert client.post(f"{AUTH}/login", json={"email": "journey@example.com", "password": "correct-horse-12"}, headers=csrf(client)).json()["seller_status"] == "ACTIVE"
    product = create(client, category_id)
    url = f"{ROOT}/{product['id']}"
    image = client.post(url + "/images", content=png(), headers={**csrf(client), "Content-Type": "image/png"})
    assert image.status_code == 201
    assert client.put(url, json=values(category_id, status="ACTIVE"), headers=csrf(client)).status_code == 200
    assert client.post(f"{AUTH}/logout", headers=csrf(client)).status_code == 204
    assert client.post(f"{AUTH}/login", json={"email": "journey@example.com", "password": "correct-horse-12"}, headers=csrf(client)).status_code == 200
    listing = client.get(ROOT + "?status=ACTIVE").json()
    assert listing["total"] == 1 and listing["items"][0]["images"][0] == image.json()
    assert client.get(image.json()["url"]).status_code == 200


def test_local_uploads_are_disabled_in_production(products_client, monkeypatch):
    client, sessions, category_id = products_client
    seller_login(client, sessions)
    product = create(client, category_id)
    headers = {**csrf(client), "Content-Type": "image/png"}
    monkeypatch.setattr(get_settings(), "environment", "production")
    response = client.post(f"{ROOT}/{product['id']}/images", content=png(), headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_UPLOADS_DEVELOPMENT_ONLY"
    assert not get_settings().product_upload_dir.exists()
