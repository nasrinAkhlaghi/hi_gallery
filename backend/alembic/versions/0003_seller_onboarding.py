"""Add seller drafts and append-only lifecycle history.

Revision ID: 0003_seller_onboarding
Revises: 0002_refresh_tokens
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_seller_onboarding"
down_revision = "0002_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_seller_status", "seller", type_="check")
    op.create_check_constraint(
        "ck_seller_status",
        "seller",
        "status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')",
    )
    op.alter_column("seller", "status", server_default=sa.text("'DRAFT'"))

    op.create_table(
        "seller_status_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("actor_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')",
            name="ck_seller_status_history_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')",
            name="ck_seller_status_history_new_status",
        ),
        sa.CheckConstraint("actor_type IN ('SELLER','ADMIN')", name="ck_seller_status_history_actor_type"),
        sa.ForeignKeyConstraint(["seller_id"], ["seller.id"]),
        sa.ForeignKeyConstraint(["actor_account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_seller_status_history_seller_created",
        "seller_status_history",
        ["seller_id", "created_at"],
    )
    op.create_index(
        "ix_seller_status_history_actor_account",
        "seller_status_history",
        ["actor_account_id"],
    )
    op.execute(
        """
        CREATE FUNCTION reject_seller_status_history_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'seller status history is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_seller_status_history_append_only
        BEFORE UPDATE OR DELETE ON seller_status_history
        FOR EACH ROW EXECUTE FUNCTION reject_seller_status_history_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_seller_status_history_no_truncate
        BEFORE TRUNCATE ON seller_status_history
        FOR EACH STATEMENT EXECUTE FUNCTION reject_seller_status_history_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM seller_status_history) THEN
                RAISE EXCEPTION 'cannot downgrade: seller lifecycle audit history exists';
            END IF;
            IF EXISTS (SELECT 1 FROM seller WHERE status = 'DRAFT') THEN
                RAISE EXCEPTION 'cannot downgrade: DRAFT sellers require the onboarding schema';
            END IF;
        END;
        $guard$
        """
    )
    op.execute("DROP TRIGGER trg_seller_status_history_no_truncate ON seller_status_history")
    op.execute("DROP TRIGGER trg_seller_status_history_append_only ON seller_status_history")
    op.execute("DROP FUNCTION reject_seller_status_history_mutation()")
    op.drop_index("ix_seller_status_history_actor_account", table_name="seller_status_history")
    op.drop_index("ix_seller_status_history_seller_created", table_name="seller_status_history")
    op.drop_table("seller_status_history")
    op.drop_constraint("ck_seller_status", "seller", type_="check")
    op.create_check_constraint(
        "ck_seller_status",
        "seller",
        "status IN ('PENDING','ACTIVE','SUSPENDED','REJECTED')",
    )
    op.alter_column("seller", "status", server_default=sa.text("'PENDING'"))
