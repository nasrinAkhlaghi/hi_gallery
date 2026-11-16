"""Compile the migration always; verify legacy data against opt-in PostgreSQL."""

import os
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def migration_config(output=None):
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"), output_buffer=output)
    config.set_main_option("script_location", str(backend / "alembic"))
    return config


def test_shop_migration_compiles_as_additive_postgresql_sql(monkeypatch):
    monkeypatch.setattr(get_settings(), "database_url", "postgresql+psycopg://unused:unused@localhost/unused")
    output = StringIO()
    command.upgrade(migration_config(output), "0003_seller_onboarding:0004_shop_settings", sql=True)
    sql = output.getvalue()
    assert "ADD COLUMN shop_category_id UUID" in sql
    assert "ADD COLUMN theme_id VARCHAR(30) DEFAULT 'gallery' NOT NULL" in sql
    assert "FOREIGN KEY(shop_category_id) REFERENCES category (id)" in sql
    assert "ck_seller_theme_id" in sql and "idx_seller_shop_category" in sql
    assert "DROP TABLE" not in sql


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL")
    or os.getenv("TEST_DATABASE_ISOLATED") != "1"
    or os.getenv("TEST_DATABASE_URL") == os.getenv("DATABASE_URL"),
    reason="requires a separate PostgreSQL database explicitly marked TEST_DATABASE_ISOLATED=1",
)
def test_shop_migration_preserves_existing_sellers_and_products(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]
    schema_name = f"shop_migration_{uuid4().hex}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    isolated = create_engine(database_url, connect_args={"options": f"-c search_path={schema_name},public"})
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema_name},public")
    monkeypatch.setattr(get_settings(), "database_url", database_url)
    try:
        config = migration_config()
        command.upgrade(config, "0003_seller_onboarding")
        with isolated.begin() as connection:
            category_id = connection.scalar(text("INSERT INTO category(name,slug) VALUES ('Clay','clay') RETURNING id"))
            for status in ("DRAFT", "PENDING", "ACTIVE", "REJECTED", "SUSPENDED"):
                account_id = connection.scalar(text(
                    "INSERT INTO account(email,password_hash) VALUES (:email,'unused') RETURNING id"
                ), {"email": f"{status.lower()}@example.com"})
                seller_id = connection.scalar(text(
                    "INSERT INTO seller(account_id,shop_name,status) VALUES (:account,'Legacy',:status) RETURNING id"
                ), {"account": account_id, "status": status})
                connection.execute(text(
                    "INSERT INTO product(seller_id,category_id,name,price,stock,status) "
                    "VALUES (:seller,:category,'Bowl',12.50,3,'ACTIVE')"
                ), {"seller": seller_id, "category": category_id})
            sellers_before = connection.execute(text("SELECT * FROM seller ORDER BY id")).mappings().all()
            products_before = connection.execute(text("SELECT * FROM product ORDER BY id")).mappings().all()
        command.upgrade(config, "0004_shop_settings")
        with isolated.connect() as connection:
            sellers_after = connection.execute(text("SELECT * FROM seller ORDER BY id")).mappings().all()
            assert [{key: row[key] for key in sellers_before[0]} for row in sellers_after] == sellers_before
            assert all(row["theme_id"] == "gallery" and row["shop_category_id"] is None for row in sellers_after)
            assert connection.execute(text("SELECT * FROM product ORDER BY id")).mappings().all() == products_before
            assert connection.scalar(text("SELECT count(*) FROM seller_status_history")) == 0
        command.downgrade(config, "0003_seller_onboarding")
        with isolated.connect() as connection:
            assert connection.execute(text("SELECT * FROM seller ORDER BY id")).mappings().all() == sellers_before
            assert connection.execute(text("SELECT * FROM product ORDER BY id")).mappings().all() == products_before
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()
