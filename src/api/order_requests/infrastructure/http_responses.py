from __future__ import annotations

from typing import Any, assert_never

from fastapi import HTTPException
from fastapi import status as http_status

from src.api.order_requests.domain import (
    OrderRequestAccessDenied,
    OrderRequestCannotAccept,
    OrderRequestCardListingNotFound,
    OrderRequestErrorResponse,
    OrderRequestInvalidTransition,
    OrderRequestItemAlreadyExists,
    OrderRequestItemCannotBeAdded,
    OrderRequestItemCannotBeRestored,
    OrderRequestInvalidQuantities,
    OrderRequestItemNotFound,
    OrderRequestNotEditable,
    OrderRequestNotFound,
)

_UNAUTHORIZED_RESPONSE = {
    "model": OrderRequestErrorResponse,
    "description": "No existe una identidad autenticada válida.",
}
_FORBIDDEN_RESPONSE = {
    "model": OrderRequestErrorResponse,
    "description": "La identidad no posee el permiso requerido.",
}
_REQUEST_NOT_FOUND_RESPONSE = {
    "model": OrderRequestErrorResponse,
    "description": "La Orden no existe o pertenece a otro Usuario.",
}
_VALIDATION_RESPONSE = {
    "description": "La entrada, paginación o filtros no cumplen el contrato.",
}
_FORBIDDEN_RESPONSE = {
    "model": OrderRequestErrorResponse,
    "description": "La transición o sus precondiciones no son válidas.",
}
STATUS_ACTION_RESPONSES: dict[int, dict[str, Any]] = {
    401: _UNAUTHORIZED_RESPONSE,
    403: _FORBIDDEN_RESPONSE,
    404: _REQUEST_NOT_FOUND_RESPONSE,
    409: _FORBIDDEN_RESPONSE,
    422: _VALIDATION_RESPONSE,
}

def _raise_request_not_found() -> None:
    raise HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail="La Orden no existe",
    )

def _raise_mutation_error(error: object) -> None:
    match error:
        case OrderRequestAccessDenied():
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para modificar Órdenes",
            )
        case OrderRequestNotFound():
            _raise_request_not_found()
        case OrderRequestItemNotFound():
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="El ítem no existe en la Orden",
            )
        case OrderRequestCardListingNotFound():
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="La publicación de carta no existe",
            )
        case OrderRequestNotEditable():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El estado actual de la Orden no permite editarla",
            )
        case OrderRequestItemCannotBeAdded():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El estado actual de la Orden no permite añadir ítems",
            )
        case OrderRequestItemCannotBeRestored():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="El ítem no puede restaurarse en el estado actual de la Orden",
            )
        case OrderRequestInvalidQuantities():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="La cantidad acordada no puede superar la cantidad solicitada",
            )
        case OrderRequestItemAlreadyExists():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="La publicación ya pertenece a la Orden; restaura su ítem si fue retirado",
            )
        case OrderRequestInvalidTransition():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="La transición solicitada no es válida para el estado actual",
            )
        case OrderRequestCannotAccept(reason="no_active_items"):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="La Orden necesita al menos un ítem activo para aceptarse",
            )
        case OrderRequestCannotAccept():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Todos los ítems activos deben tener precios completos",
            )
        case unexpected:
            assert_never(unexpected)
