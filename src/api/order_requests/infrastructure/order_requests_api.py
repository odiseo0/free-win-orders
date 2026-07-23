from __future__ import annotations

from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.order_periods.domain import OrderPeriodNotFound
from src.api.order_requests.application import order_request_cases
from src.api.order_requests.domain import (
    OrderRequestAccessDenied,
    OrderRequestCardListingNotFound,
    OrderRequestCreate,
    OrderRequestHistoryResponse,
    OrderRequestItemCreate,
    OrderRequestItemPricingUpdate,
    OrderRequestItemUpdate,
    OrderRequestListResponse,
    OrderRequestNotFound,
    OrderRequestPeriodNotOpen,
    OrderRequestResponse,
    OrderRequestStatus,
    OrderRequestUpdate,
)
from src.api.roles.domain import Actor, PermissionCode
from src.api.roles.infrastructure.auth import get_current_user, require_actor
from src.core import Err, Ok
from src.core.db import get_db
from .http_responses import STATUS_ACTION_RESPONSES, _VALIDATION_RESPONSE, _FORBIDDEN_RESPONSE, _REQUEST_NOT_FOUND_RESPONSE, _UNAUTHORIZED_RESPONSE, _raise_mutation_error, _raise_request_not_found

router = APIRouter(tags=["order-requests"])

@router.post(
    "/",
    status_code=http_status.HTTP_201_CREATED,
    response_model=OrderRequestResponse,
    summary="Enviar una Orden",
    description=(
        "Crea una Orden propia dentro de un Pedido abierto. Todas las publicaciones "
        "de carta deben existir antes de guardar la Orden."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def create_order_request(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_CREATE_SELF)),
    ],
    request_in: OrderRequestCreate,
) -> OrderRequestResponse:
    result = await order_request_cases.create(db, actor, request_in)

    match result:
        case Ok(request):
            return request
        case Err(OrderRequestAccessDenied()):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para crear Órdenes",
            )
        case Err(OrderPeriodNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El Pedido no existe",
            )
        case Err(OrderRequestCardListingNotFound()):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="La publicación de carta no existe",
            )
        case Err(OrderRequestPeriodNotOpen()):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El Pedido no está abierto para recibir Órdenes",
            )
        case unexpected:
            assert_never(unexpected)


@router.patch(
    "/{order_request_id}",
    response_model=OrderRequestResponse,
    summary="Actualizar la nota compartida de una Orden",
    description=(
        "Sustituye o elimina la nota compartida. La Orden se bloquea durante la "
        "operación y solo se auditan cambios efectivos."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def update_order_request_note(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    request_in: OrderRequestUpdate,
) -> OrderRequestResponse:
    result = await order_request_cases.update_note(
        db, actor, order_request_id, request_in
    )

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/items",
    status_code=http_status.HTTP_201_CREATED,
    response_model=OrderRequestResponse,
    summary="Añadir un ítem a una Orden",
    description=(
        "Añade una publicación existente y copia su snapshot en servidor. Una "
        "publicación retirada debe recuperarse mediante la acción restore."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def add_order_request_item(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    item_in: OrderRequestItemCreate,
) -> OrderRequestResponse:
    result = await order_request_cases.add_item(db, actor, order_request_id, item_in)

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.patch(
    "/{order_request_id}/items/{item_id}",
    response_model=OrderRequestResponse,
    summary="Actualizar las cantidades de un ítem",
    description=(
        "Actualiza la cantidad solicitada y/o acordada de un ítem activo. No acepta "
        "campos de precios administrativos."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def update_order_request_item(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    item_in: OrderRequestItemUpdate,
) -> OrderRequestResponse:
    result = await order_request_cases.update_item(
        db, actor, order_request_id, item_id, item_in
    )

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/items/{item_id}/remove",
    response_model=OrderRequestResponse,
    summary="Retirar un ítem de una Orden",
    description=(
        "Retira lógicamente el ítem sin perder su snapshot ni sus precios. Si era "
        "el último ítem activo, cancela la Orden en la misma transacción."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def remove_order_request_item(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.remove_item(
        db, actor, order_request_id, item_id
    )

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/items/{item_id}/restore",
    response_model=OrderRequestResponse,
    summary="Restaurar un ítem retirado",
    description=(
        "Reactiva un ítem retirado. En una Orden aceptada solo se permite cuando "
        "los tres componentes de precio definitivo ya están completos."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def restore_order_request_item(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.restore_item(
        db, actor, order_request_id, item_id
    )

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/start-review",
    response_model=OrderRequestResponse,
    summary="Iniciar la revisión administrativa",
    description=(
        "Cambia una Orden submitted a in_review. Requiere el permiso administrativo "
        "de revisión y bloquea la Orden durante toda la transición."
    ),
    responses=STATUS_ACTION_RESPONSES,
)
async def start_order_request_review(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_REVIEW)),
    ],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.start_review(db, actor, order_request_id)

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/accept",
    response_model=OrderRequestResponse,
    summary="Aceptar una Orden revisada",
    description=(
        "Acepta una Orden in_review cuando conserva al menos un ítem activo y los "
        "tres componentes de precio están completos en todos ellos."
    ),
    responses=STATUS_ACTION_RESPONSES,
)
async def accept_order_request(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_REVIEW)),
    ],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.accept(db, actor, order_request_id)
    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/reject",
    response_model=OrderRequestResponse,
    summary="Rechazar una Orden",
    description=(
        "Rechaza administrativamente una Orden submitted o in_review y registra "
        "la transición en su historial."
    ),
    responses=STATUS_ACTION_RESPONSES,
)
async def reject_order_request(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_REVIEW)),
    ],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.reject(db, actor, order_request_id)

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/cancel",
    response_model=OrderRequestResponse,
    summary="Cancelar una Orden",
    description=(
        "Permite al propietario cancelar su Orden submitted, in_review o accepted. "
        "Una identidad administrativa solo puede cancelarla donde lo permite la matriz."
    ),
    responses=STATUS_ACTION_RESPONSES,
)
async def cancel_order_request(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.cancel(db, actor, order_request_id)

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.post(
    "/{order_request_id}/reopen-for-review",
    response_model=OrderRequestResponse,
    summary="Reabrir una Orden para revisión",
    description=(
        "Devuelve administrativamente una Orden accepted, rejected o cancelled a "
        "in_review. Al reabrir una cancelada elimina sus marcas de cancelación."
    ),
    responses=STATUS_ACTION_RESPONSES,
)
async def reopen_order_request_for_review(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_REVIEW)),
    ],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.reopen_for_review(db, actor, order_request_id)

    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.patch(
    "/{order_request_id}/items/{item_id}/pricing",
    response_model=OrderRequestResponse,
    summary="Fijar el precio definitivo de un ítem",
    description=(
        "Sustituye los componentes unitarios de carta, envío e impuesto. El precio "
        "unitario final y los totales se calculan en servidor; cero es válido."
    ),
    responses=STATUS_ACTION_RESPONSES
)
async def update_order_request_item_pricing(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        Actor,
        Depends(require_actor(PermissionCode.ORDER_REQUESTS_REVIEW)),
    ],
    order_request_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    pricing_in: OrderRequestItemPricingUpdate,
) -> OrderRequestResponse:
    result = await order_request_cases.update_pricing(
        db,
        actor,
        order_request_id,
        item_id,
        pricing_in,
    )
    match result:
        case Ok(request):
            return request
        case Err(error):
            _raise_mutation_error(error)


@router.get(
    "/",
    response_model=OrderRequestListResponse,
    summary="Listar Órdenes visibles",
    description=(
        "Devuelve únicamente las Órdenes propias para un Usuario convencional. "
        "Una identidad con permiso global puede consultar todas las Órdenes."
    ),
    responses={
        401: _UNAUTHORIZED_RESPONSE,
        403: _FORBIDDEN_RESPONSE,
        422: _VALIDATION_RESPONSE,
    },
)
async def read_order_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
    order_period_id: Annotated[int | None, Query(alias="orderPeriodId", gt=0)] = None,
    status: OrderRequestStatus | None = None,
) -> OrderRequestListResponse:
    result = await order_request_cases.get_multi(
        db,
        actor,
        page=page,
        shows=shows,
        order_period_id=order_period_id,
        status=status,
    )

    match result:
        case Ok((requests, total)):
            return OrderRequestListResponse(items=requests, total=total)
        case Err(OrderRequestAccessDenied()):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para consultar Órdenes",
            )
        case unexpected:
            assert_never(unexpected)


@router.get(
    "/{order_request_id}/history",
    response_model=list[OrderRequestHistoryResponse],
    summary="Consultar el historial de una Orden",
    description=(
        "Devuelve los eventos visibles de la Orden, del más reciente al más antiguo. "
        "Una Orden ajena se presenta como inexistente."
    ),
    responses={
        401: _UNAUTHORIZED_RESPONSE,
        403: _FORBIDDEN_RESPONSE,
        404: _REQUEST_NOT_FOUND_RESPONSE,
        422: _VALIDATION_RESPONSE,
    },
)
async def read_order_request_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[OrderRequestHistoryResponse]:
    result = await order_request_cases.get_history(
        db,
        actor,
        order_request_id,
        page=page,
        shows=shows,
    )

    match result:
        case Ok(history):
            return history
        case Err(OrderRequestAccessDenied()):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para consultar Órdenes",
            )
        case Err(OrderRequestNotFound()):
            _raise_request_not_found()
        case unexpected:
            assert_never(unexpected)


@router.get(
    "/{order_request_id}",
    response_model=OrderRequestResponse,
    summary="Consultar una Orden",
    description=(
        "Devuelve una Orden propia o cualquier Orden cuando la identidad posee "
        "permiso global. Una Orden ajena se presenta como inexistente."
    ),
    responses={
        401: _UNAUTHORIZED_RESPONSE,
        403: _FORBIDDEN_RESPONSE,
        404: _REQUEST_NOT_FOUND_RESPONSE,
        422: _VALIDATION_RESPONSE,
    },
)
async def read_order_request(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: Annotated[int, Path(gt=0)],
) -> OrderRequestResponse:
    result = await order_request_cases.get_one(db, actor, order_request_id)

    match result:
        case Ok(request):
            return request
        case Err(OrderRequestAccessDenied()):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para consultar Órdenes",
            )
        case Err(OrderRequestNotFound()):
            _raise_request_not_found()
        case unexpected:
            assert_never(unexpected)
