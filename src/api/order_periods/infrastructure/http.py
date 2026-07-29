from __future__ import annotations

from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Query
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
from src.core.schema import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.core.utils.utils import datetime_now

router = APIRouter(tags=["order-periods"])

type OrderPeriodId = Annotated[
    int,
    Path(gt=0, description="Identificador positivo del Pedido."),
]

_ORDER_PERIOD_NOT_FOUND_RESPONSE = {
    **NOT_FOUND_RESPONSE,
    "description": "El Pedido no existe o no es visible para la identidad actual.",
}
_DATE_CONFLICT_RESPONSE = {
    **CONFLICT_RESPONSE,
    "description": "Las fechas no son compatibles con el estado actual del Pedido.",
    "content": {
        "application/json": {
            "example": {
                "detail": (
                    "Las fechas del Pedido entran en conflicto con su estado actual"
                )
            }
        }
    },
}
_UPDATE_CONFLICT_RESPONSE = {
    **CONFLICT_RESPONSE,
    "description": "El estado actual del Pedido no permite el cambio solicitado.",
    "content": {
        "application/json": {
            "example": {"detail": "El Pedido no admite ese cambio en su estado actual"}
        }
    },
}
_CLOSE_CONFLICT_RESPONSE = {
    **CONFLICT_RESPONSE,
    "description": "El Pedido ya está cerrado o todavía permanece en borrador.",
    "content": {
        "application/json": {
            "examples": {
                "alreadyClosed": {
                    "summary": "Pedido cerrado",
                    "value": {"detail": "El Pedido ya está cerrado"},
                },
                "draft": {
                    "summary": "Pedido en borrador",
                    "value": {"detail": "Un Pedido en borrador no se puede cerrar"},
                },
            }
        }
    },
}
_AUTHENTICATED_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    422: VALIDATION_RESPONSE,
}


async def _get_visible_period(
    db: AsyncSession,
    actor: Actor,
    order_period_id: int,
) -> OrderPeriod:
    result = await order_period_cases.get_one(db, order_period_id)

    match result:
        case Ok(period):
            period_status = resolve_order_period_status(
                period.opens_at,
                period.closes_at,
                datetime_now(),
            )
            decision = can_read_order_period(
                actor,
                is_draft=period_status is OrderPeriodStatus.DRAFT,
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
    operation_id="createOrderPeriod",
    summary="Crear un Pedido",
    description=(
        "Crea un Pedido administrado por la identidad actual. Permanece en borrador "
        "hasta `opensAt`; las fechas deben incluir zona horaria y la apertura debe "
        "ser anterior al cierre."
    ),
    responses={
        **_AUTHENTICATED_RESPONSES,
        409: _DATE_CONFLICT_RESPONSE,
    },
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


@router.get(
    "/",
    status_code=http_status.HTTP_200_OK,
    response_model=OrderPeriodListResponse,
    operation_id="listOrderPeriods",
    summary="Listar Pedidos visibles",
    description=(
        "Devuelve los Pedidos que la identidad puede consultar. Los borradores "
        "requieren visibilidad administrativa y pueden filtrarse por estado calculado."
    ),
    responses=_AUTHENTICATED_RESPONSES,
)
async def read_order_periods(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_READ))],
    page: Annotated[
        int,
        Query(ge=1, description="Página solicitada; la primera página es 1."),
    ] = 1,
    shows: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Cantidad máxima de Pedidos por página.",
        ),
    ] = 100,
    status: Annotated[
        OrderPeriodStatus | None,
        Query(description="Limita el listado al estado calculado indicado."),
    ] = None,
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
    status_code=http_status.HTTP_200_OK,
    response_model=list[OrderPeriodHistoryResponse],
    operation_id="getOrderPeriodHistory",
    summary="Consultar el historial de un Pedido",
    description=(
        "Devuelve los eventos del Pedido del más reciente al más antiguo. Un borrador "
        "sin visibilidad administrativa se presenta como inexistente."
    ),
    responses={
        **_AUTHENTICATED_RESPONSES,
        404: _ORDER_PERIOD_NOT_FOUND_RESPONSE,
    },
)
async def read_order_period_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    order_period_id: OrderPeriodId,
    page: Annotated[
        int,
        Query(ge=1, description="Página solicitada; la primera página es 1."),
    ] = 1,
    shows: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Cantidad máxima de eventos por página.",
        ),
    ] = 100,
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


@router.get(
    "/{order_period_id}",
    status_code=http_status.HTTP_200_OK,
    response_model=OrderPeriodResponse,
    operation_id="getOrderPeriod",
    summary="Consultar un Pedido",
    description=(
        "Devuelve el Pedido y su estado calculado. Un borrador que la identidad no "
        "puede consultar se presenta como inexistente."
    ),
    responses={
        **_AUTHENTICATED_RESPONSES,
        404: _ORDER_PERIOD_NOT_FOUND_RESPONSE,
    },
)
async def read_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_READ))],
    order_period_id: OrderPeriodId,
) -> OrderPeriodResponse:
    return await _get_visible_period(db, actor, order_period_id)


@router.patch(
    "/{order_period_id}",
    status_code=http_status.HTTP_200_OK,
    response_model=OrderPeriodResponse,
    operation_id="updateOrderPeriod",
    summary="Actualizar un Pedido",
    description=(
        "Actualiza únicamente los campos enviados. Los campos no aceptan `null`; "
        "las fechas deben incluir zona horaria y algunos cambios dejan de estar "
        "permitidos después de la apertura o el cierre."
    ),
    responses={
        **_AUTHENTICATED_RESPONSES,
        404: _ORDER_PERIOD_NOT_FOUND_RESPONSE,
        409: _UPDATE_CONFLICT_RESPONSE,
    },
)
async def update_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_UPDATE))
    ],
    order_period_id: OrderPeriodId,
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


@router.post(
    "/{order_period_id}/close",
    status_code=http_status.HTTP_200_OK,
    response_model=OrderPeriodResponse,
    operation_id="closeOrderPeriod",
    summary="Cerrar anticipadamente un Pedido",
    description=(
        "Cierra un Pedido abierto antes de `closesAt` y registra el evento. No puede "
        "cerrar un borrador ni volver a cerrar un Pedido finalizado."
    ),
    responses={
        **_AUTHENTICATED_RESPONSES,
        404: _ORDER_PERIOD_NOT_FOUND_RESPONSE,
        409: _CLOSE_CONFLICT_RESPONSE,
    },
)
async def close_order_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(require_actor(PermissionCode.ORDER_PERIODS_CLOSE))],
    order_period_id: OrderPeriodId,
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
