from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from src.core.db import Base, Date
from src.core.utils.utils import datetime_now


class DeliveryStage(Date, Base, kw_only=True):
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_delivery_stages_scope_key"),
        CheckConstraint(
            "scope IN ('international', 'national', 'pickup')", name="valid_scope"
        ),
        CheckConstraint("kind IN ('progress', 'exception')", name="valid_kind"),
        CheckConstraint("position >= 0", name="non_negative_position"),
        Index("ix_delivery_stages_scope_position", "scope", "position"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="progress")
    is_terminal: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )


class DeliveryShipment(Date, Base, kw_only=True):
    __table_args__ = (
        UniqueConstraint("fulfillment_id", name="uq_delivery_shipments_fulfillment"),
        CheckConstraint(
            "kind IN ('international', 'national')", name="valid_kind"
        ),
        CheckConstraint(
            "(kind = 'international' AND order_period_id IS NOT NULL "
            "AND fulfillment_id IS NULL) OR "
            "(kind = 'national' AND order_period_id IS NULL "
            "AND fulfillment_id IS NOT NULL)",
            name="valid_owner",
        ),
        Index("ix_delivery_shipments_order_period_id", "order_period_id"),
        Index("ix_delivery_shipments_fulfillment_id", "fulfillment_id"),
        Index("ix_delivery_shipments_carrier_tracking", "carrier", "tracking_number"),
        Index("ix_delivery_shipments_next_check_at", "next_check_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    order_period_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("order_periods.id"), default=None, nullable=True
    )
    fulfillment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_fulfillments.id", ondelete="CASCADE"),
        default=None,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(150))
    reference: Mapped[str | None] = mapped_column(
        String(150), default=None, nullable=True
    )
    external_references: Mapped[list[str]] = mapped_column(
        JSONB, default_factory=list
    )
    current_stage_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_stages.id")
    )
    carrier: Mapped[str | None] = mapped_column(
        String(30), default=None, nullable=True
    )
    tracking_number: Mapped[str | None] = mapped_column(
        String(100), default=None, nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        default=None, nullable=True
    )
    next_check_at: Mapped[datetime | None] = mapped_column(
        default=None, nullable=True
    )
    refresh_requested_at: Mapped[datetime | None] = mapped_column(
        default=None, nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        String(100), default=None, nullable=True
    )
    failure_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    current_stage: Mapped[DeliveryStage] = relationship(
        lazy="joined", innerjoin=True, init=False
    )
    allocations: Mapped[list[DeliveryShipmentAllocation]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", init=False
    )
    events: Mapped[list[DeliveryEvent]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", init=False
    )
    fulfillment: Mapped[DeliveryFulfillment | None] = relationship(
        back_populates="shipment", init=False
    )


class DeliveryShipmentAllocation(MappedAsDataclass, Base, kw_only=True):
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "order_request_item_id",
            name="uq_delivery_shipment_allocations_shipment_item",
        ),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        Index(
            "ix_delivery_shipment_allocations_order_request_id",
            "order_request_id",
        ),
        Index(
            "ix_delivery_shipment_allocations_order_request_item_id",
            "order_request_item_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    shipment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_shipments.id", ondelete="CASCADE")
    )
    order_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_requests.id")
    )
    order_request_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_request_items.id")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    shipment: Mapped[DeliveryShipment] = relationship(
        back_populates="allocations", init=False
    )


class DeliveryPreference(Date, Base, kw_only=True):
    __table_args__ = (
        UniqueConstraint("order_request_id", name="uq_delivery_preferences_request"),
        CheckConstraint(
            "method IN ('pickup', 'national_shipping')", name="valid_method"
        ),
        CheckConstraint(
            "method != 'pickup' OR user_address_id IS NULL",
            name="valid_address",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_requests.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(30))
    user_address_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_addresses.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )


class DeliveryFulfillment(Date, Base, kw_only=True):
    __table_args__ = (
        CheckConstraint(
            "method IN ('pickup', 'national_shipping')", name="valid_method"
        ),
        CheckConstraint(
            "shipping_cost IS NULL OR shipping_cost >= 0",
            name="non_negative_shipping_cost",
        ),
        Index("ix_delivery_fulfillments_order_request_id", "order_request_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_requests.id")
    )
    method: Mapped[str] = mapped_column(String(30))
    current_stage_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("delivery_stages.id")
    )
    recipient_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, default=None, nullable=True
    )
    address_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, default=None, nullable=True
    )
    shipping_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None, nullable=True
    )
    currency: Mapped[str | None] = mapped_column(
        String(3), default=None, nullable=True
    )
    cost_payer: Mapped[str | None] = mapped_column(
        String(20), default=None, nullable=True
    )
    current_stage: Mapped[DeliveryStage] = relationship(
        lazy="joined", innerjoin=True, init=False
    )
    shipment: Mapped[DeliveryShipment | None] = relationship(
        back_populates="fulfillment",
        uselist=False,
        cascade="all, delete-orphan",
        init=False,
    )
    events: Mapped[list[DeliveryEvent]] = relationship(
        back_populates="fulfillment", cascade="all, delete-orphan", init=False
    )


class DeliveryEvent(MappedAsDataclass, Base, kw_only=True):
    __table_args__ = (
        CheckConstraint(
            "(shipment_id IS NOT NULL) <> (fulfillment_id IS NOT NULL)",
            name="one_owner",
        ),
        CheckConstraint(
            "source IN ('admin', 'system', 'carrier')", name="valid_source"
        ),
        UniqueConstraint(
            "shipment_id", "fingerprint", name="uq_delivery_events_shipment_fingerprint"
        ),
        Index("ix_delivery_events_shipment_occurred", "shipment_id", "occurred_at"),
        Index(
            "ix_delivery_events_fulfillment_occurred",
            "fulfillment_id",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    shipment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_shipments.id", ondelete="CASCADE"),
        default=None,
        nullable=True,
    )
    fulfillment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_fulfillments.id", ondelete="CASCADE"),
        default=None,
        nullable=True,
    )
    stage_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("delivery_stages.id"), default=None, nullable=True
    )
    stage_key: Mapped[str | None] = mapped_column(
        String(50), default=None, nullable=True
    )
    stage_name: Mapped[str | None] = mapped_column(
        String(100), default=None, nullable=True
    )
    source: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), default=None, nullable=True
    )
    occurred_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(default_factory=datetime_now)
    note: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    raw_status: Mapped[str | None] = mapped_column(
        Text, default=None, nullable=True
    )
    fingerprint: Mapped[str | None] = mapped_column(
        String(128), default=None, nullable=True
    )
    correction_of_event_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("delivery_events.id"),
        default=None,
        nullable=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(
        Text, default=None, nullable=True
    )
    shipment: Mapped[DeliveryShipment | None] = relationship(
        back_populates="events", foreign_keys=[shipment_id], init=False
    )
    fulfillment: Mapped[DeliveryFulfillment | None] = relationship(
        back_populates="events", foreign_keys=[fulfillment_id], init=False
    )
