from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import false, select

from src.api.order_periods.domain import (
    OrderPeriodCreate,
    OrderPeriodStatus,
    OrderPeriodUpdate,
)
from src.core.db import DAO
from src.core.utils.utils import Empty, EmptyType

from .models import OrderPeriod

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderPeriodDAO(DAO[OrderPeriod, OrderPeriodCreate, OrderPeriodUpdate]):
    async def get_for_update(
        self,
        db: AsyncSession,
        order_period_id: int,
    ) -> OrderPeriod | EmptyType:
        statement = (
            select(self.model)
            .where(self.model.id == order_period_id)
            .with_for_update()
        )
        period = (await db.execute(statement)).scalar_one_or_none()
        return period if period is not None else Empty

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        page: int,
        shows: int,
        status: OrderPeriodStatus | None,
        now: datetime,
        include_drafts: bool,
        ordering: list[tuple[str, bool]],
    ) -> tuple[list[OrderPeriod], int]:
        conditions = []

        if status is OrderPeriodStatus.DRAFT:
            conditions.append(self.model.opens_at > now if include_drafts else false())
        elif status is OrderPeriodStatus.OPEN:
            conditions.extend([self.model.opens_at <= now, self.model.closes_at > now])
        elif status is OrderPeriodStatus.CLOSED:
            conditions.append(self.model.closes_at <= now)
        elif not include_drafts:
            conditions.append(self.model.opens_at <= now)

        statement = select(self.model).where(*conditions)
        ordered = self.order_by(statement, ordering)
        total = await self.count(db, statement)
        periods = (await db.execute(ordered.offset(page).limit(shows))).scalars().all()

        return list(periods), total


class OrderPeriodHistoryDAO:
    pass


dao_order_period_histories = OrderPeriodHistoryDAO()
dao_order_periods = OrderPeriodDAO(OrderPeriod)
