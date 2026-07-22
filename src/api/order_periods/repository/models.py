from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column, relationship

from src.core.db import Base, Date


class OrderPeriod(MappedAsDataclass, Base, Date, kw_only=True):
    __table_args__ = (
        CheckConstraint("opens_at < closes_at", name="valid_date_range"),
        Index("ix_order_periods_opens_at", "opens_at"),
        Index("ix_order_periods_closes_at", "closes_at"),
        Index("ix_order_periods_created_by_user_id", "created_by_user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255))
    opens_at: Mapped[datetime]
    closes_at: Mapped[datetime]
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    history: Mapped[list[OrderPeriodHistory]] = relationship(
        back_populates="order_period",
        cascade="all, delete-orphan",
        init=False,
    )


class OrderPeriodHistory(MappedAsDataclass, Base, kw_only=True):
    __table_args__ = (
        CheckConstraint(
            "event IN ('created', 'updated', 'closed_early')",
            name="valid_event",
        ),
        Index(
            "ix_order_period_histories_period_occurred",
            "order_period_id",
            "occurred_at",
        ),
        Index("ix_order_period_histories_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, init=False, autoincrement=True, primary_key=True
    )
    order_period_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_periods.id", ondelete="CASCADE")
    )
    event: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    occurred_at: Mapped[datetime]
    changes: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    order_period: Mapped[OrderPeriod] = relationship(
        back_populates="history", init=False
    )
