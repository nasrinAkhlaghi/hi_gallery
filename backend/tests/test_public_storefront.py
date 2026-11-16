"""Signed-out shop/product contracts, publication visibility and discovery filters."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Account, Category, Product, ProductImage, Seller
from app.db.session import Base, get_db
from app.main import app

API = "/api/v1"
ID_OFFSET = 0xA << 124


def product_uuid(number):
    # Include a hex letter so SQLite does not coerce UUID text into a number.
    return UUID(int=ID_OFFSET + number)


@pytest.fixture
def storefront():
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
    ids = {key: uuid4() for key in ("owner", "seller", "other", "empty", "category", "disabled", "child")}
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        for owner in ("owner", "other", "empty"):
            session.add(Account(id=ids[owner], email=f"{owner}@example.com", password_hash="private-hash",
                                status="ACTIVE", created_at=now, updated_at=now))
        for key, status in (("category", "ACTIVE"), ("disabled", "INACTIVE")):
            session.add(Category(id=ids[key], name=key, slug=key, status=status, created_at=now, updated_at=now))
        session.flush()
        session.add(Category(id=ids["child"], parent_id=ids["category"], name="Child", slug="child", status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        session.add(Seller(id=ids["seller"], account_id=ids["owner"], shop_name="Handmade Studio", description="Made by hand",
                           logo_url="https://example.com/logo.png", shop_category_id=ids["child"], theme_id="clay", status="ACTIVE", created_at=now, updated_at=now))
        for owner in ("other", "empty"):
            session.add(Seller(id=ids[owner], account_id=ids[owner], shop_name=owner, status="ACTIVE", created_at=now, updated_at=now))
        session.flush()
        for number, name, category, status, stock in (
            (1, "Clay Bowl", "category", "ACTIVE", 5),
            (2, "Clay Cup", "category", "ACTIVE", 0),
            (3, "100%_ / vase", "disabled", "SOLD_OUT", 0),
            (4, "Hidden Clay", "category", "DRAFT", 2),
            (5, "Inactive Clay", "category", "INACTIVE", 2),
            (6, "Clay child", "child", "ACTIVE", 2),
            (7, "Clay other", "category", "ACTIVE", 2),
        ):
            session.add(Product(id=product_uuid(number), seller_id=ids["other"] if number == 7 else ids["seller"],
                                category_id=ids[category], name=name, description="Handmade", price="12.50", stock=stock,
                                status=status, created_at=now + timedelta(seconds=1 if number == 6 else 0), updated_at=now))
        session.flush()
        for number, position in ((3, 3), (2, 0), (1, 0)):
            session.add(ProductImage(id=product_uuid(1000 + number), product_id=product_uuid(1), url=f"/media/products/{number}.png", sort_order=position))

    def override_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, sessions, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def product_ids(response):
    assert response.status_code == 200, response.text
    return [(UUID(item["id"]).int - ID_OFFSET) for item in response.json()["items"]]


def test_signed_out_shop_and_product_responses_are_explicit_public_projections(storefront):
    client, _, ids = storefront
    shop = client.get(f"{API}/shops/{ids['seller']}")
    assert shop.status_code == 200
    assert set(shop.json()) == {"id", "shop_name", "description", "logo_url", "category", "theme_id"}
    assert shop.json()["theme_id"] == "clay"
    assert shop.json()["category"]["id"] == str(ids["child"])
    product = client.get(f"{API}/products/{product_uuid(1)}")
    assert product.status_code == 200
    data = product.json()
    assert set(data) == {"id", "name", "description", "category", "price", "stock", "status", "images", "seller"}
    assert data["price"] == "12.50"
    assert data["seller"] == {"id": str(ids["seller"]), "shop_name": "Handmade Studio"}
    assert set(data["category"]) == {"id", "parent_id", "name", "slug"}
    assert [(UUID(image["id"]).int - ID_OFFSET) for image in data["images"]] == [1001, 1002, 1003]
    assert all(set(image) == {"id", "url", "sort_order"} for image in data["images"])
    assert product_ids(client.get(f"{API}/products")) == [6, 1, 2, 3, 7]
    # Every list returns exactly the same safe product projection as detail.
    for path in ("products", f"shops/{ids['seller']}/products", f"categories/{ids['category']}/products"):
        listing = client.get(f"{API}/{path}").json()
        assert next(item for item in listing["items"] if item["id"] == str(product_uuid(1))) == data


@pytest.mark.parametrize("seller_status,account_status,product_status", [
    ("ACTIVE", "ACTIVE", "ACTIVE"), ("ACTIVE", "ACTIVE", "SOLD_OUT"),
    ("ACTIVE", "ACTIVE", "DRAFT"), ("ACTIVE", "ACTIVE", "INACTIVE"),
    ("DRAFT", "ACTIVE", "ACTIVE"), ("PENDING", "ACTIVE", "ACTIVE"),
    ("REJECTED", "ACTIVE", "ACTIVE"), ("SUSPENDED", "ACTIVE", "ACTIVE"),
    ("ACTIVE", "SUSPENDED", "ACTIVE"), ("ACTIVE", "DELETED", "ACTIVE"),
])
def test_all_public_paths_apply_the_same_visibility(storefront, seller_status, account_status, product_status):
    client, sessions, ids = storefront
    with sessions.begin() as session:
        session.get(Seller, ids["seller"]).status = seller_status
        session.get(Account, ids["owner"]).status = account_status
        session.get(Product, product_uuid(1)).status = product_status
    shop_visible = seller_status == "ACTIVE" and account_status == "ACTIVE"
    product_visible = shop_visible and product_status in {"ACTIVE", "SOLD_OUT"}
    assert client.get(f"{API}/products/{product_uuid(1)}").status_code == (200 if product_visible else 404)
    assert client.get(f"{API}/shops/{ids['seller']}").status_code == (200 if shop_visible else 404)
    shop_listing = client.get(f"{API}/shops/{ids['seller']}/products")
    if not shop_visible:
        assert shop_listing.status_code == 404
    else:
        assert (1 in product_ids(shop_listing)) is product_visible
    for path in ("products", f"categories/{ids['category']}/products"):
        response = client.get(f"{API}/{path}")
        assert (1 in product_ids(response)) is product_visible
        if not shop_visible:
            assert product_ids(response) == [7]
            assert response.json()["total"] == 1


def test_hidden_product_ids_return_404_even_with_seller_only_status_query(storefront):
    client, _, _ = storefront
    for identity in (product_uuid(4), product_uuid(5), uuid4()):
        assert client.get(f"{API}/products/{identity}").status_code == 404
    assert product_ids(client.get(f"{API}/products", params={"status": "DRAFT"})) == [6, 1, 2, 3, 7]


def test_exact_category_filters_and_shop_category_independence(storefront):
    client, _, ids = storefront
    assert product_ids(client.get(f"{API}/products", params={"category_id": str(ids["category"])})) == [1, 2, 7]
    assert product_ids(client.get(f"{API}/categories/{ids['category']}/products")) == [1, 2, 7]
    assert product_ids(client.get(f"{API}/shops/{ids['seller']}/products", params={"category_id": str(ids["category"])})) == [1, 2]
    assert product_ids(client.get(f"{API}/shops/{ids['seller']}/products", params={"category_id": str(ids["child"])})) == [6]
    assert product_ids(client.get(f"{API}/products", params={"category_id": str(uuid4())})) == []
    # Disabled categories do not hide published products, but are not navigable.
    assert client.get(f"{API}/products/{product_uuid(3)}").status_code == 200
    assert product_ids(client.get(f"{API}/products", params={"category_id": str(ids["disabled"])})) == [3]
    assert ids["disabled"] not in [UUID(item["id"]) for item in client.get(f"{API}/categories").json()["items"]]
    for identity in (ids["disabled"], uuid4()):
        assert client.get(f"{API}/categories/{identity}/products").status_code == 404


@pytest.mark.parametrize("search,expected", [
    ("  cLaY  ", [6, 1, 2, 7]), ("%", [3]), ("_", [3]), ("/", [3]),
    ("%_ /", [3]), ("", [6, 1, 2, 3, 7]), ("   ", [6, 1, 2, 3, 7]),
    ("no match", []), ("' OR 1=1 --", []),
])
def test_search_is_trimmed_case_insensitive_and_literal(storefront, search, expected):
    client, _, _ = storefront
    response = client.get(f"{API}/products", params={"q": search})
    assert product_ids(response) == expected
    assert response.json()["total"] == len(expected)


def test_search_category_and_pagination_compose_with_stable_order_and_visible_totals(storefront):
    client, _, ids = storefront
    params = {"q": "clay", "category_id": str(ids["category"]), "page_size": 1}
    for page, identity in enumerate((1, 2, 7)):
        response = client.get(f"{API}/products", params={**params, "page": page})
        assert product_ids(response) == [identity]
        assert response.json()["total"] == 3
        assert response.json()["page"] == page
        assert response.json()["page_size"] == 1
    assert product_ids(client.get(f"{API}/products", params={**params, "page": 3})) == []
    for path, expected in (("products", [6, 1, 2, 3, 7]),
                           (f"shops/{ids['seller']}/products", [6, 1, 2, 3]),
                           (f"categories/{ids['category']}/products", [1, 2, 7])):
        first = client.get(f"{API}/{path}", params={"page_size": 2})
        second = client.get(f"{API}/{path}", params={"page_size": 2, "page": 1})
        assert product_ids(first) == expected[:2]
        assert product_ids(second) == expected[2:4]
        assert first.json()["total"] == second.json()["total"] == len(expected)


def test_empty_and_legacy_shops_and_disabled_primary_category(storefront):
    client, sessions, ids = storefront
    empty = client.get(f"{API}/shops/{ids['empty']}")
    assert empty.status_code == 200
    assert empty.json()["theme_id"] == "gallery" and empty.json()["category"] is None
    listing = client.get(f"{API}/shops/{ids['empty']}/products")
    assert product_ids(listing) == [] and listing.json()["total"] == 0
    for suffix in ("", "/products"):
        assert client.get(f"{API}/shops/{uuid4()}{suffix}").status_code == 404
    with sessions.begin() as session:
        session.get(Category, ids["child"]).status = "INACTIVE"
    assert client.get(f"{API}/shops/{ids['seller']}").json()["category"] is None
    assert product_ids(client.get(f"{API}/shops/{ids['seller']}/products")) == [6, 1, 2, 3]


@pytest.mark.parametrize("query", [{"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "invalid"}])
def test_invalid_pagination_is_rejected_on_every_list(storefront, query):
    client, _, ids = storefront
    for path in ("products", f"shops/{ids['seller']}/products", f"categories/{ids['category']}/products"):
        assert client.get(f"{API}/{path}", params=query).status_code == 422


def test_invalid_identifiers_search_and_category_filters_return_422(storefront):
    client, _, ids = storefront
    for path in ("products/bad", "shops/bad", "shops/bad/products", "categories/bad/products"):
        assert client.get(f"{API}/{path}").status_code == 422
    for path in ("products", f"shops/{ids['seller']}/products"):
        assert client.get(f"{API}/{path}", params={"category_id": "bad"}).status_code == 422
    assert client.get(f"{API}/products", params={"q": "x" * 201}).status_code == 422
    assert client.get(f"{API}/products", params={"q": "  " + "x" * 200 + "  "}).status_code == 200


def test_sold_out_and_zero_stock_are_visible_without_status_rewrites(storefront):
    client, sessions, _ = storefront
    for number, expected in ((2, "ACTIVE"), (3, "SOLD_OUT")):
        response = client.get(f"{API}/products/{product_uuid(number)}")
        assert response.status_code == 200
        assert (response.json()["status"], response.json()["stock"]) == (expected, 0)
        with sessions() as session:
            assert session.get(Product, product_uuid(number)).status == expected
