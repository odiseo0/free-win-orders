from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Never, cast

from src.api.order_periods.domain import (
    OrderPeriodAlreadyClosed,
    OrderPeriodCannotCloseDraft,
    OrderPeriodCreate,
    OrderPeriodDateConflict,
    OrderPeriodEventType,
    OrderPeriodImmutableField,
    OrderPeriodNotFound,
    OrderPeriodStatus,
    OrderPeriodUpdate,
    resolve_order_period_status,
)
from src.api.order_periods.repository import dao_order_period_histories as history_dao
from src.api.order_periods.repository import dao_order_periods as dao
from src.api.order_periods.repository import OrderPeriodHistory
from src.api.roles.domain import Actor, PermissionCode
from src.core import Err, Ok, Result
from src.core.db import DAOError
from src.core.utils.utils import Empty, datetime_now

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.api.order_periods.repository import OrderPeriod


type OrderPeriodMutationError = (
    OrderPeriodNotFound
    | OrderPeriodDateConflict
    | OrderPeriodImmutableField
    | OrderPeriodAlreadyClosed
)


def _serialized_change(field: str, old: object, new: object) -> dict[str, object]:
    def serialize(value: object) -> object:
        return value.isoformat() if isinstance(value, datetime) else value

    return {
        "field": field,
        "oldValue": serialize(old),
        "newValue": serialize(new),
    }


def _effective_update(
    period: OrderPeriod, period_in: OrderPeriodUpdate
) -> tuple[dict[str, datetime | Any], list[dict[str, datetime | Any]]]:
    values: dict[str, object] = {}
    changes: list[dict[str, object]] = []
    public_names = {
        "name": "name",
        "opens_at": "opensAt",
        "closes_at": "closesAt",
    }

    for field in ("name", "opens_at", "closes_at"):
        if field not in period_in.model_fields_set:
            continue

        new_value = getattr(period_in, field)
        old_value = getattr(period, field)

        if new_value == old_value:
            continue

        values[field] = new_value
        changes.append(_serialized_change(public_names[field], old_value, new_value))

    return values, changes


async def get_one(
    db: AsyncSession, order_period_id: int
) -> Result[OrderPeriod, OrderPeriodNotFound]:
    period = await dao.get(db, order_period_id)

    if period is Empty:
        return Err(OrderPeriodNotFound(order_period_id))

    return Ok(period)


async def get_multi(
    db: AsyncSession,
    actor: Actor,
    *,
    page: int = 1,
    shows: int = 100,
    status: OrderPeriodStatus | None = None,
) -> Result[tuple[list[OrderPeriod], int], Never]:
    now = datetime_now()
    include_drafts = PermissionCode.ORDER_PERIODS_READ_DRAFTS in actor.permissions
    periods, total = await dao.get_multi(
        db,
        page=(page - 1) * shows,
        shows=shows,
        status=status,
        now=now,
        include_drafts=include_drafts,
        ordering=[("date_added", True)],
    )

    return Ok((periods, total))


async def create(
    db: AsyncSession,
    actor: Actor,
    period_in: OrderPeriodCreate,
) -> Result[OrderPeriod, OrderPeriodDateConflict]:
    now = datetime_now()

    if period_in.closes_at <= now:
        return Err(OrderPeriodDateConflict())

    try:
        period = await dao.create(
            db,
            obj_in={
                **period_in.model_dump(mode="python"),
                "created_by_user_id": actor.user_id,
            },
            commit=False,
        )
        await history_dao.add(
            db,
            OrderPeriodHistory(
                order_period_id=period.id,
                event=OrderPeriodEventType.CREATED,
                actor_user_id=actor.user_id,
                occurred_at=now,
                changes=[],
            ),
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(period)


async def update(
    db: AsyncSession,
    actor: Actor,
    order_period_id: int,
    period_in: OrderPeriodUpdate,
) -> Result[OrderPeriod, OrderPeriodMutationError]:
    now = datetime_now()
    period = await dao.get_for_update(db, order_period_id)

    if period is Empty:
        return Err(OrderPeriodNotFound(order_period_id))

    period = cast("OrderPeriod", period)
    status = resolve_order_period_status(period.opens_at, period.closes_at, now)

    if status is OrderPeriodStatus.CLOSED:
        return Err(OrderPeriodAlreadyClosed(order_period_id))

    values, changes = _effective_update(period, period_in)

    if not values:
        return Ok(period)

    if status is OrderPeriodStatus.OPEN:
        for field in ("name", "opens_at"):
            if field in values:
                return Err(OrderPeriodImmutableField(field))

    period = cast("OrderPeriod", period)
    opens_at = values.get("opens_at", period.opens_at)
    closes_at = values.get("closes_at", period.closes_at)

    if opens_at >= closes_at or closes_at <= now:
        return Err(OrderPeriodDateConflict())

    try:
        updated = await dao.update(
            db,
            period.id,
            values,
            commit=False,
        )
        await history_dao.add(
            db,
            OrderPeriodHistory(
                order_period_id=order_period_id,
                event=OrderPeriodEventType.UPDATED,
                actor_user_id=actor.user_id,
                occurred_at=now,
                changes=changes,
            ),
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(updated)


async def close(
    db: AsyncSession,
    actor: Actor,
    order_period_id: int,
) -> Result[
    OrderPeriod,
    OrderPeriodNotFound | OrderPeriodCannotCloseDraft | OrderPeriodAlreadyClosed,
]:
    now = datetime_now()
    period = await dao.get_for_update(db, order_period_id)

    if period is Empty:
        return Err(OrderPeriodNotFound(order_period_id))

    period = cast("OrderPeriod", period)
    status = resolve_order_period_status(period.opens_at, period.closes_at, now)

    if status is OrderPeriodStatus.DRAFT:
        return Err(OrderPeriodCannotCloseDraft(order_period_id))
    if status is OrderPeriodStatus.CLOSED:
        return Err(OrderPeriodAlreadyClosed(order_period_id))

    changes = [_serialized_change("closesAt", period.closes_at, now)]

    try:
        updated = await dao.update(
            db,
            period.id,
            {"closes_at": now},
            commit=False,
        )
        await history_dao.add(
            db,
            OrderPeriodHistory(
                order_period_id=order_period_id,
                event=OrderPeriodEventType.CLOSED_EARLY,
                actor_user_id=actor.user_id,
                occurred_at=now,
                changes=changes,
            ),
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(updated)


async def get_history(
    db: AsyncSession,
    order_period_id: int,
    *,
    page: int = 1,
    shows: int = 100,
) -> Result[list[OrderPeriodHistory], OrderPeriodNotFound]:
    period = await dao.get(db, order_period_id)

    if period is Empty:
        return Err(OrderPeriodNotFound(order_period_id))

    history = await history_dao.get_for_period(
        db,
        order_period_id,
        page=(page - 1) * shows,
        shows=shows,
    )

    return Ok(history)
