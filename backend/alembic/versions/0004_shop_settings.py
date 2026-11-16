"""Add seller shop category and built-in theme.

Revision ID: 0004_shop_settings
Revises: 0003_seller_onboarding
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_shop_settings"
down_revision = "0003_seller_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller", sa.Column("shop_category_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("seller", sa.Column("theme_id", sa.String(30), nullable=False, server_default=sa.text("'gallery'")))
    op.create_foreign_key("fk_seller_shop_category", "seller", "category", ["shop_category_id"], ["id"])
    op.create_check_constraint("ck_seller_theme_id", "seller", "theme_id IN ('gallery','linen','clay')")
    op.create_index("idx_seller_shop_category", "seller", ["shop_category_id"])


def downgrade() -> None:
    op.drop_index("idx_seller_shop_category", table_name="seller")
    op.drop_constraint("ck_seller_theme_id", "seller", type_="check")
    op.drop_constraint("fk_seller_shop_category", "seller", type_="foreignkey")
    op.drop_column("seller", "theme_id")
    op.drop_column("seller", "shop_category_id")
