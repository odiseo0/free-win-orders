from __future__ import annotations

from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.order_periods.application import order_period_cases
from src.api.order_periods.domain import (
    OrderPeriodAlreadyClosed,
    OrderPeriodCannotCloseDraft,
    OrderPeriodCreate,
    OrderPeriodDateConflict,
    OrderPeriodHistoryResponse,
    OrderPeriodImmutableField,
    OrderPeriodListResponse,
    OrderPeriodNotFound,
    OrderPeriodResponse,
    OrderPeriodStatus,
    OrderPeriodUpdate,
    can_read_order_period,
    resolve_order_period_status,
)
from src.api.order_periods.repository import OrderPeriod
from src.api.roles.domain import Actor, AuthorizationDecision, PermissionCode
from src.api.roles.infrastructure.auth import enforce_decision, require_actor
from src.core import Err, Ok
from src.core.db import get_db
from src.core.utils.utils import datetime_now

router = APIRouter(tags=["order-periods"])


async def _get_visible_period(
    db: AsyncSession,
    actor: Actor,
    order_period_id: int,
) -> OrderPeriod:
    result = await order_period_cases.get_one(db, order_period_id)

    match result:
        case Ok(period):
            decision = can_read_order_period(
                actor,
                is_draft=resolve_order_period_status(
                    period.opens_at,
                    period.closes_at,
                    datetime_now(),
                )
                is OrderPeriodStatus.DRAFT,
            )

            if decision is AuthorizationDecision.HIDDEN:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="El Pedido no existe",
                )

            enforce_decision(decision)

            return period
        case Err(OrderPeriodNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El Pedido no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.post(
    "/",
    status_code=http_status.HTTP_201_CREATED,
    response_model=OrderPeriodResponse,
)
async def create_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_CREATE))
    ],
    period_in: OrderPeriodCreate,
) -> OrderPeriodResponse:
    result = await order_period_cases.create(db, actor, period_in)

    match result:
        case Ok(period):
            return period
        case Err(OrderPeriodDateConflict()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Las fechas del Pedido entran en conflicto con su estado actual",
            )
        case unexpected:
            assert_never(unexpected)


@router.get("/", response_model=OrderPeriodListResponse)
async def read_order_periods(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_READ))],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
    status: OrderPeriodStatus | None = None,
) -> OrderPeriodListResponse:
    result = await order_period_cases.get_multi(
        db, actor, page=page, shows=shows, status=status
    )

    match result:
        case Ok((periods, total)):
            return {"items": periods, "total": total}
        case Err(error):
            assert_never(error)


@router.get(
    "/{order_period_id}/history",
    response_model=list[OrderPeriodHistoryResponse],
)
async def read_order_period_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_READ))],
    order_period_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[OrderPeriodHistoryResponse]:
    await _get_visible_period(db, actor, order_period_id)

    result = await order_period_cases.get_history(
        db, order_period_id, page=page, shows=shows
    )

    match result:
        case Ok(history):
            return history
        case Err(OrderPeriodNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El Pedido no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.get("/{order_period_id}", response_model=OrderPeriodResponse)
async def read_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_READ))],
    order_period_id: int,
) -> OrderPeriodResponse:
    return await _get_visible_period(db, actor, order_period_id)


@router.patch("/{order_period_id}", response_model=OrderPeriodResponse)
async def update_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_UPDATE))
    ],
    order_period_id: int,
    period_in: OrderPeriodUpdate,
) -> OrderPeriodResponse:
    result = await order_period_cases.update(db, actor, order_period_id, period_in)

    match result:
        case Ok(period):
            return period
        case Err(OrderPeriodNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El Pedido no existe",
            )
        case Err(OrderPeriodImmutableField()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El Pedido no admite ese cambio en su estado actual",
            )
        case Err(OrderPeriodDateConflict()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Las fechas del Pedido entran en conflicto con su estado actual",
            )
        case Err(OrderPeriodAlreadyClosed()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El Pedido ya está cerrado",
            )
        case unexpected:
            assert_never(unexpected)


@router.post("/{order_period_id}/close", response_model=OrderPeriodResponse)
async def close_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_CLOSE))],
    order_period_id: int,
) -> OrderPeriodResponse:
    result = await order_period_cases.close(db, actor, order_period_id)

    match result:
        case Ok(period):
            return period
        case Err(OrderPeriodNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El Pedido no existe",
            )
        case Err(OrderPeriodAlreadyClosed()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El Pedido ya está cerrado",
            )
        case Err(OrderPeriodCannotCloseDraft()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Un Pedido en borrador no se puede cerrar",
            )
        case unexpected:
            assert_never(unexpected)
