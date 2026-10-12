import re
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers

from app.db import models  # noqa: F401 - importing registers every mapped entity
from app.db.session import Base

EXPECTED_TABLES = {
    "account", "buyer", "seller", "admin", "category", "product", "product_image",
    "cart", "cart_item", "orders", "seller_order", "order_item", "payment", "review",
}


def test_all_documented_entities_are_registered_with_alembic_metadata() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    configure_mappers()


def test_migration_schema_snapshot_matches_authoritative_document() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    migration_schema = (repository_root / "backend" / "alembic" / "schema.sql").read_text(encoding="utf-8")
    documented_schema = (repository_root / "docs" / "04-database-schema.sql").read_text(encoding="utf-8")

    assert migration_schema == documented_schema


def test_model_columns_and_named_indexes_match_documented_schema() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "alembic" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    documented_tables = {
        table_name: body
        for table_name, body in re.findall(r"CREATE TABLE (\w+)\s*\((.*?)\n\);", schema, re.DOTALL)
    }

    assert set(documented_tables) == EXPECTED_TABLES
    for table_name, body in documented_tables.items():
        documented_columns = set(
            re.findall(r"^\s{4}([a-z_]+)\s+(?:UUID|VARCHAR|TEXT|TIMESTAMPTZ|NUMERIC|INTEGER|SMALLINT)\b", body, re.MULTILINE)
        )
        assert set(Base.metadata.tables[table_name].columns.keys()) == documented_columns

    documented_indexes = set(re.findall(r"CREATE INDEX (\w+) ON", schema))
    model_indexes = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert model_indexes == documented_indexes

    documented_check_names = set(re.findall(r"CONSTRAINT (ck_\w+) CHECK", schema))
    model_check_names = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert model_check_names == documented_check_names


def test_documented_foreign_keys_and_unique_constraints_match_metadata() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "alembic" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    documented_tables = {
        table_name: body
        for table_name, body in re.findall(r"CREATE TABLE (\w+)\s*\((.*?)\n\);", schema, re.DOTALL)
    }

    for table_name, body in documented_tables.items():
        expected_foreign_keys: set[tuple[str, str]] = set()
        for local_column, target_table, target_column in re.findall(
            r"^\s{4}([a-z_]+)\s+[^\n]*?REFERENCES\s+([a-z_]+)\(([a-z_]+)\)", body, re.MULTILINE
        ):
            expected_foreign_keys.add((local_column, f"{target_table}.{target_column}"))
        for local_columns, target_table, target_columns in re.findall(
            r"FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+([a-z_]+)\(([^)]+)\)", body
        ):
            expected_foreign_keys.update(
                (local.strip(), f"{target_table}.{target.strip()}")
                for local, target in zip(local_columns.split(","), target_columns.split(","), strict=True)
            )

        actual_foreign_keys = {
            (foreign_key.parent.name, foreign_key.target_fullname)
            for foreign_key in Base.metadata.tables[table_name].foreign_keys
        }
        assert actual_foreign_keys == expected_foreign_keys

        expected_unique_sets = {
            (column,)
            for column, remainder in re.findall(
                r"^\s{4}([a-z_]+)\s+([^\n]*)$", body, re.MULTILINE
            )
            if re.search(r"\bUNIQUE\b", remainder)
        }
        expected_unique_sets.update(
            tuple(column.strip() for column in columns.split(","))
            for columns in re.findall(r"UNIQUE\s*\(([^)]+)\)", body)
        )
        actual_unique_sets = {
            tuple(column.name for column in constraint.columns)
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert actual_unique_sets == expected_unique_sets


def test_documented_column_types_and_nullability_match_metadata() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "alembic" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    documented_tables = {
        table_name: body
        for table_name, body in re.findall(r"CREATE TABLE (\w+)\s*\((.*?)\n\);", schema, re.DOTALL)
    }
    dialect = postgresql.dialect()

    for table_name, body in documented_tables.items():
        for column_name, documented_type, remainder in re.findall(
            r"^\s{4}([a-z_]+)\s+(UUID|VARCHAR\(\d+\)|TEXT|TIMESTAMPTZ|NUMERIC\(\d+,\s*\d+\)|INTEGER|SMALLINT)(?=\s|$)([^\n]*)",
            body,
            re.MULTILINE,
        ):
            column = Base.metadata.tables[table_name].columns[column_name]
            model_type = dialect.type_compiler.process(column.type).upper().replace(" ", "")
            expected_type = documented_type.upper().replace(" ", "")
            if expected_type == "TIMESTAMPTZ":
                expected_type = "TIMESTAMPWITHTIMEZONE"
            assert model_type == expected_type
            expected_nullable = "NOT NULL" not in remainder.upper() and "PRIMARY KEY" not in remainder.upper()
            assert column.nullable is expected_nullable


def test_documented_composite_order_item_ownership_foreign_keys_are_mapped() -> None:
    order_item = Base.metadata.tables["order_item"]
    foreign_key_pairs = {
        (foreign_key.parent.name, foreign_key.target_fullname)
        for foreign_key in order_item.foreign_keys
    }
    assert {
        ("seller_order_id", "seller_order.id"),
        ("seller_id", "seller_order.seller_id"),
        ("product_id", "product.id"),
        ("seller_id", "product.seller_id"),
    } <= foreign_key_pairs
