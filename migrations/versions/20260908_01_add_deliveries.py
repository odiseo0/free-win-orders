"""Add payment and delivery tracking.

Revision ID: 20260908_01
Revises: 20260814_01
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_01"
down_revision: str | Sequence[str] | None = "20260814_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


STAGES = (
    ("international", "purchase_confirmed", "Compra confirmada", 0, False, "progress"),
    ("international", "to_us_courier", "Hacia courier en USA", 10, False, "progress"),
    ("international", "at_us_courier", "Recibido por courier", 20, False, "progress"),
    ("international", "to_venezuela", "Hacia Venezuela", 30, False, "progress"),
    ("international", "received_by_admin", "Recibido por administrador", 40, False, "progress"),
    ("international", "organized", "Organizado", 50, True, "progress"),
    ("national", "preparing", "Preparando", 0, False, "progress"),
    ("national", "handed_to_carrier", "Entregado a la empresa", 10, False, "progress"),
    ("national", "in_transit", "En tránsito", 20, False, "progress"),
    ("national", "ready_for_pickup", "Listo para retirar", 30, False, "progress"),
    ("national", "delivered", "Entregado", 40, True, "progress"),
    ("national", "exception", "Con incidencia", 100, False, "exception"),
    ("pickup", "ready_for_pickup", "Listo para retirar", 0, False, "progress"),
    ("pickup", "picked_up", "Retirado", 10, True, "progress"),
)


def upgrade() -> None:
    op.drop_constraint("ck_order_requests_valid_status", "order_requests", type_="check")
    op.create_check_constraint(
        "ck_order_requests_valid_status",
        "order_requests",
        "status IN ('submitted', 'in_review', 'accepted', 'paid', 'rejected', 'cancelled')",
    )
    op.add_column("order_requests", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_requests", sa.Column("paid_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("order_requests", sa.Column("purchasing_finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_requests", sa.Column("purchasing_finalized_by_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f("fk_order_requests_paid_by_user_id_users"), "order_requests", "users", ["paid_by_user_id"], ["id"])
    op.create_foreign_key(op.f("fk_order_requests_purchasing_finalized_by_user_id_users"), "order_requests", "users", ["purchasing_finalized_by_user_id"], ["id"])
    op.create_check_constraint("ck_order_requests_consistent_payment_audit", "order_requests", "(paid_at IS NULL) = (paid_by_user_id IS NULL)")
    op.create_check_constraint("ck_order_requests_consistent_purchasing_audit", "order_requests", "(purchasing_finalized_at IS NULL) = (purchasing_finalized_by_user_id IS NULL)")

    op.create_table(
        "delivery_stages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="progress"),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('international', 'national', 'pickup')", name=op.f("ck_delivery_stages_valid_scope")),
        sa.CheckConstraint("kind IN ('progress', 'exception')", name=op.f("ck_delivery_stages_valid_kind")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_delivery_stages_non_negative_position")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_stages")),
        sa.UniqueConstraint("scope", "key", name="uq_delivery_stages_scope_key"),
    )
    stage_table = sa.table(
        "delivery_stages",
        sa.column("scope", sa.String), sa.column("key", sa.String),
        sa.column("name", sa.String), sa.column("position", sa.Integer),
        sa.column("is_terminal", sa.Boolean), sa.column("kind", sa.String),
    )
    op.bulk_insert(stage_table, [dict(zip(("scope", "key", "name", "position", "is_terminal", "kind"), row, strict=True)) for row in STAGES])
    op.create_index("ix_delivery_stages_scope_position", "delivery_stages", ["scope", "position"])

    op.create_table(
        "delivery_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_request_id", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("user_address_id", sa.BigInteger(), nullable=True),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("method IN ('pickup', 'national_shipping')", name=op.f("ck_delivery_preferences_valid_method")),
        sa.CheckConstraint("method != 'pickup' OR user_address_id IS NULL", name=op.f("ck_delivery_preferences_valid_address")),
        sa.ForeignKeyConstraint(["order_request_id"], ["order_requests.id"], ondelete="CASCADE", name=op.f("fk_delivery_preferences_order_request_id_order_requests")),
        sa.ForeignKeyConstraint(["user_address_id"], ["user_addresses.id"], ondelete="SET NULL", name=op.f("fk_delivery_preferences_user_address_id_user_addresses")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_preferences")),
        sa.UniqueConstraint("order_request_id", name="uq_delivery_preferences_request"),
    )
    op.create_table(
        "delivery_fulfillments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_request_id", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("current_stage_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("address_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("cost_payer", sa.String(20), nullable=True),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("method IN ('pickup', 'national_shipping')", name=op.f("ck_delivery_fulfillments_valid_method")),
        sa.CheckConstraint("shipping_cost IS NULL OR shipping_cost >= 0", name=op.f("ck_delivery_fulfillments_non_negative_shipping_cost")),
        sa.ForeignKeyConstraint(["current_stage_id"], ["delivery_stages.id"], name=op.f("fk_delivery_fulfillments_current_stage_id_delivery_stages")),
        sa.ForeignKeyConstraint(["order_request_id"], ["order_requests.id"], name=op.f("fk_delivery_fulfillments_order_request_id_order_requests")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_fulfillments")),
    )
    op.create_index("ix_delivery_fulfillments_order_request_id", "delivery_fulfillments", ["order_request_id"])
    op.create_table(
        "delivery_shipments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("order_period_id", sa.BigInteger(), nullable=True),
        sa.Column("fulfillment_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("reference", sa.String(150), nullable=True),
        sa.Column("external_references", postgresql.JSONB(), nullable=False),
        sa.Column("current_stage_id", sa.BigInteger(), nullable=False),
        sa.Column("carrier", sa.String(30), nullable=True),
        sa.Column("tracking_number", sa.String(100), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(100), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('international', 'national')", name=op.f("ck_delivery_shipments_valid_kind")),
        sa.CheckConstraint("(kind = 'international' AND order_period_id IS NOT NULL AND fulfillment_id IS NULL) OR (kind = 'national' AND order_period_id IS NULL AND fulfillment_id IS NOT NULL)", name=op.f("ck_delivery_shipments_valid_owner")),
        sa.ForeignKeyConstraint(["current_stage_id"], ["delivery_stages.id"], name=op.f("fk_delivery_shipments_current_stage_id_delivery_stages")),
        sa.ForeignKeyConstraint(["fulfillment_id"], ["delivery_fulfillments.id"], ondelete="CASCADE", name=op.f("fk_delivery_shipments_fulfillment_id_delivery_fulfillments")),
        sa.ForeignKeyConstraint(["order_period_id"], ["order_periods.id"], name=op.f("fk_delivery_shipments_order_period_id_order_periods")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_shipments")),
        sa.UniqueConstraint("fulfillment_id", name="uq_delivery_shipments_fulfillment"),
    )
    for name, columns in (
        ("ix_delivery_shipments_order_period_id", ["order_period_id"]),
        ("ix_delivery_shipments_fulfillment_id", ["fulfillment_id"]),
        ("ix_delivery_shipments_carrier_tracking", ["carrier", "tracking_number"]),
        ("ix_delivery_shipments_next_check_at", ["next_check_at"]),
    ):
        op.create_index(name, "delivery_shipments", columns)
    op.create_table(
        "delivery_shipment_allocations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("shipment_id", sa.BigInteger(), nullable=False),
        sa.Column("order_request_id", sa.BigInteger(), nullable=False),
        sa.Column("order_request_item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_delivery_shipment_allocations_positive_quantity")),
        sa.ForeignKeyConstraint(["shipment_id"], ["delivery_shipments.id"], ondelete="CASCADE", name=op.f("fk_delivery_shipment_allocations_shipment_id_delivery_shipments")),
        sa.ForeignKeyConstraint(["order_request_id"], ["order_requests.id"], name=op.f("fk_delivery_shipment_allocations_order_request_id_order_requests")),
        sa.ForeignKeyConstraint(["order_request_item_id"], ["order_request_items.id"], name=op.f("fk_delivery_shipment_allocations_order_request_item_id_order_request_items")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_shipment_allocations")),
        sa.UniqueConstraint("shipment_id", "order_request_item_id", name="uq_delivery_shipment_allocations_shipment_item"),
    )
    op.create_index("ix_delivery_shipment_allocations_order_request_id", "delivery_shipment_allocations", ["order_request_id"])
    op.create_index("ix_delivery_shipment_allocations_order_request_item_id", "delivery_shipment_allocations", ["order_request_item_id"])
    op.create_table(
        "delivery_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("shipment_id", sa.BigInteger(), nullable=True),
        sa.Column("fulfillment_id", sa.BigInteger(), nullable=True),
        sa.Column("stage_id", sa.BigInteger(), nullable=True),
        sa.Column("stage_key", sa.String(50), nullable=True),
        sa.Column("stage_name", sa.String(100), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("raw_status", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(128), nullable=True),
        sa.Column("correction_of_event_id", sa.BigInteger(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("(shipment_id IS NOT NULL) <> (fulfillment_id IS NOT NULL)", name=op.f("ck_delivery_events_one_owner")),
        sa.CheckConstraint("source IN ('admin', 'system', 'carrier')", name=op.f("ck_delivery_events_valid_source")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_delivery_events_actor_user_id_users")),
        sa.ForeignKeyConstraint(["correction_of_event_id"], ["delivery_events.id"], name=op.f("fk_delivery_events_correction_of_event_id_delivery_events")),
        sa.ForeignKeyConstraint(["fulfillment_id"], ["delivery_fulfillments.id"], ondelete="CASCADE", name=op.f("fk_delivery_events_fulfillment_id_delivery_fulfillments")),
        sa.ForeignKeyConstraint(["shipment_id"], ["delivery_shipments.id"], ondelete="CASCADE", name=op.f("fk_delivery_events_shipment_id_delivery_shipments")),
        sa.ForeignKeyConstraint(["stage_id"], ["delivery_stages.id"], name=op.f("fk_delivery_events_stage_id_delivery_stages")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_events")),
        sa.UniqueConstraint("shipment_id", "fingerprint", name="uq_delivery_events_shipment_fingerprint"),
    )
    op.create_index("ix_delivery_events_shipment_occurred", "delivery_events", ["shipment_id", "occurred_at"])
    op.create_index("ix_delivery_events_fulfillment_occurred", "delivery_events", ["fulfillment_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("delivery_events")
    op.drop_table("delivery_shipment_allocations")
    op.drop_table("delivery_shipments")
    op.drop_table("delivery_fulfillments")
    op.drop_table("delivery_preferences")
    op.drop_table("delivery_stages")
    op.drop_constraint("ck_order_requests_consistent_purchasing_audit", "order_requests", type_="check")
    op.drop_constraint("ck_order_requests_consistent_payment_audit", "order_requests", type_="check")
    op.drop_constraint(op.f("fk_order_requests_purchasing_finalized_by_user_id_users"), "order_requests", type_="foreignkey")
    op.drop_constraint(op.f("fk_order_requests_paid_by_user_id_users"), "order_requests", type_="foreignkey")
    op.drop_column("order_requests", "purchasing_finalized_by_user_id")
    op.drop_column("order_requests", "purchasing_finalized_at")
    op.drop_column("order_requests", "paid_by_user_id")
    op.drop_column("order_requests", "paid_at")
    op.drop_constraint("ck_order_requests_valid_status", "order_requests", type_="check")
    op.execute("UPDATE order_requests SET status = 'accepted' WHERE status = 'paid'")
    op.create_check_constraint(
        "ck_order_requests_valid_status",
        "order_requests",
        "status IN ('submitted', 'in_review', 'accepted', 'rejected', 'cancelled')",
    )
