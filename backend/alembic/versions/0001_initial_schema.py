"""Create the PostgreSQL schema documented for HI Gallery.

Revision ID: 0001_initial_schema
Revises:
"""

from pathlib import Path

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    for statement in schema.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in (
        "review", "payment", "order_item", "seller_order", "orders",
        "cart_item", "cart", "product_image", "product", "category",
        "admin", "seller", "buyer", "account",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
