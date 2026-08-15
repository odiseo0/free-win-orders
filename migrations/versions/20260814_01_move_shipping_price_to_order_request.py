"""Move the fixed shipping price from items to the Order.

Revision ID: 20260814_01
Revises: ceb773a87f58
Create Date: 2026-08-14

Existing per-item shipping values are not migrated because they represented a
different, multiplicative pricing rule. Existing Orders keep ``shipping_price``
as NULL until an administrator establishes the fixed total during review.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_01"
down_revision: str | Sequence[str] | None = "ceb773a87f58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_requests",
        sa.Column("shipping_price", sa.Numeric(12, 2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_order_requests_non_negative_shipping_price"),
        "order_requests",
        "shipping_price IS NULL OR shipping_price >= 0",
    )

    op.drop_constraint(
        op.f("ck_order_request_items_non_negative_final_prices"),
        "order_request_items",
        type_="check",
    )
    op.drop_column("order_request_items", "shipping_unit_price")
    op.create_check_constraint(
        op.f("ck_order_request_items_non_negative_final_prices"),
        "order_request_items",
        "(card_unit_price IS NULL OR card_unit_price >= 0) AND "
        "(tax_unit_price IS NULL OR tax_unit_price >= 0)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_order_request_items_non_negative_final_prices"),
        "order_request_items",
        type_="check",
    )
    op.add_column(
        "order_request_items",
        sa.Column("shipping_unit_price", sa.Numeric(12, 2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_order_request_items_non_negative_final_prices"),
        "order_request_items",
        "(card_unit_price IS NULL OR card_unit_price >= 0) AND "
        "(shipping_unit_price IS NULL OR shipping_unit_price >= 0) AND "
        "(tax_unit_price IS NULL OR tax_unit_price >= 0)",
    )

    op.drop_constraint(
        op.f("ck_order_requests_non_negative_shipping_price"),
        "order_requests",
        type_="check",
    )
    op.drop_column("order_requests", "shipping_price")
