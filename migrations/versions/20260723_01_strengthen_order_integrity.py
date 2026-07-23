"""Strengthen Order integrity and allow unlinked scraped listings.

Revision ID: 20260723_01
Revises: b3a7ea35b324
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260723_01"
down_revision: str | Sequence[str] | None = "b3a7ea35b324"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_card_listings_card_id_cards",
        "card_listings",
        type_="foreignkey",
    )
    op.alter_column("card_listings", "card_id", nullable=True)
    op.alter_column("card_listings", "ygo_id", nullable=True)
    op.create_foreign_key(
        "fk_card_listings_card_id_cards",
        "card_listings",
        "cards",
        ["card_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_order_requests_consistent_cancelled_status",
        "order_requests",
        "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_order_requests_consistent_cancellation_audit",
        "order_requests",
        "(cancelled_at IS NULL) = (cancelled_by_user_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_order_request_items_agreed_quantity_not_above_requested",
        "order_request_items",
        "agreed_quantity <= requested_quantity",
    )
    op.create_check_constraint(
        "ck_order_request_items_consistent_removal_audit",
        "order_request_items",
        "(removed_at IS NULL) = (removed_by_user_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_order_request_items_consistent_removal_audit",
        "order_request_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_order_request_items_agreed_quantity_not_above_requested",
        "order_request_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_order_requests_consistent_cancellation_audit",
        "order_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_order_requests_consistent_cancelled_status",
        "order_requests",
        type_="check",
    )

    op.drop_constraint(
        "fk_card_listings_card_id_cards",
        "card_listings",
        type_="foreignkey",
    )
    op.alter_column("card_listings", "ygo_id", nullable=False)
    op.alter_column("card_listings", "card_id", nullable=False)
    op.create_foreign_key(
        "fk_card_listings_card_id_cards",
        "card_listings",
        "cards",
        ["card_id"],
        ["id"],
    )
