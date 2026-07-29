from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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


class OrderRequest(MappedAsDataclass, Base, Date, kw_only=True):
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'in_review', 'accepted', 'rejected', 'cancelled')",
            name="valid_status",
        ),
        CheckConstraint("currency = 'USD'", name="valid_currency"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="consistent_cancelled_status",
        ),
        CheckConstraint(
            "(cancelled_at IS NULL) = (cancelled_by_user_id IS NULL)",
            name="consistent_cancellation_audit",
        ),
        Index("ix_order_requests_order_period_id", "order_period_id"),
        Index("ix_order_requests_created_by_user_id", "created_by_user_id"),
        Index("ix_order_requests_status", "status"),
        Index(
            "ix_order_requests_period_status",
            "order_period_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_period_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_periods.id")
    )
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        String(20), default="submitted", server_default="submitted"
    )
    note: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), default="USD", server_default="USD"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        default=None,
        nullable=True,
    )
    items: Mapped[list[OrderRequestItem]] = relationship(
        back_populates="order_request",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
    )
    history: Mapped[list[OrderRequestHistory]] = relationship(
        back_populates="order_request",
        cascade="all, delete-orphan",
        init=False,
    )


class OrderRequestItem(MappedAsDataclass, Base, Date, kw_only=True):
    __table_args__ = (
        UniqueConstraint(
            "order_request_id",
            "card_listing_id",
            name="uq_order_request_items_request_listing",
        ),
        CheckConstraint(
            "requested_quantity > 0",
            name="positive_requested_quantity",
        ),
        CheckConstraint(
            "agreed_quantity >= 0",
            name="non_negative_agreed_quantity",
        ),
        CheckConstraint(
            "agreed_quantity <= requested_quantity",
            name="agreed_quantity_not_above_requested",
        ),
        CheckConstraint(
            "estimated_unit_price >= 0",
            name="non_negative_estimated_unit_price",
        ),
        CheckConstraint(
            "(card_unit_price IS NULL OR card_unit_price >= 0) AND "
            "(shipping_unit_price IS NULL OR shipping_unit_price >= 0) AND "
            "(tax_unit_price IS NULL OR tax_unit_price >= 0)",
            name="non_negative_final_prices",
        ),
        CheckConstraint(
            "(removed_at IS NULL) = (removed_by_user_id IS NULL)",
            name="consistent_removal_audit",
        ),
        Index("ix_order_request_items_order_request_id", "order_request_id"),
        Index("ix_order_request_items_card_listing_id", "card_listing_id"),
        Index(
            "ix_order_request_items_request_removed",
            "order_request_id",
            "removed_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_requests.id", ondelete="CASCADE"),
    )
    card_listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("card_listings.id"),
    )
    card_name: Mapped[str] = mapped_column(String(255))
    card_set: Mapped[str] = mapped_column(String(255))
    card_code: Mapped[str] = mapped_column(String(64))
    rarity: Mapped[str] = mapped_column(String(100))
    condition: Mapped[str] = mapped_column(String(50))
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    requested_quantity: Mapped[int] = mapped_column(Integer)
    agreed_quantity: Mapped[int] = mapped_column(Integer)
    card_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None, nullable=True
    )
    shipping_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None, nullable=True
    )
    tax_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None, nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(default=None, nullable=True)
    removed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        default=None,
        nullable=True,
    )
    order_request: Mapped[OrderRequest] = relationship(
        back_populates="items",
        init=False,
    )


class OrderRequestHistory(MappedAsDataclass, Base, kw_only=True):
    __table_args__ = (
        CheckConstraint(
            "event IN ('created', 'updated', 'status_changed', 'item_added', "
            "'item_updated', 'item_removed', 'item_restored')",
            name="valid_event",
        ),
        Index(
            "ix_order_request_histories_request_occurred",
            "order_request_id",
            "occurred_at",
        ),
        Index("ix_order_request_histories_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_requests.id", ondelete="CASCADE"),
    )
    event: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    occurred_at: Mapped[datetime]
    changes: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        default_factory=list,
    )
    order_request: Mapped[OrderRequest] = relationship(
        back_populates="history",
        init=False,
    )
