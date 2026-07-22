"""add order periods and their history

Revision ID: 20260722_02
Revises: 20260722_01
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_02"
down_revision: str | None = "20260722_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_periods",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "date_added",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "opens_at < closes_at", name=op.f("ck_order_periods_valid_date_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_order_periods_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_periods")),
    )
    op.create_index(
        "ix_order_periods_opens_at", "order_periods", ["opens_at"], unique=False
    )
    op.create_index(
        "ix_order_periods_closes_at", "order_periods", ["closes_at"], unique=False
    )
    op.create_index(
        "ix_order_periods_created_by_user_id",
        "order_periods",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "order_period_histories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_period_id", sa.BigInteger(), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event IN ('created', 'updated', 'closed_early')",
            name=op.f("ck_order_period_histories_valid_event"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_order_period_histories_actor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["order_period_id"],
            ["order_periods.id"],
            name=op.f(
                "fk_order_period_histories_order_period_id_order_periods"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_period_histories")),
    )
    op.create_index(
        "ix_order_period_histories_actor_user_id",
        "order_period_histories",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_period_histories_period_occurred",
        "order_period_histories",
        ["order_period_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_period_histories_period_occurred",
        table_name="order_period_histories",
    )
    op.drop_index(
        "ix_order_period_histories_actor_user_id",
        table_name="order_period_histories",
    )
    op.drop_table("order_period_histories")
    op.drop_index("ix_order_periods_created_by_user_id", table_name="order_periods")
    op.drop_index("ix_order_periods_closes_at", table_name="order_periods")
    op.drop_index("ix_order_periods_opens_at", table_name="order_periods")
    op.drop_table("order_periods")
