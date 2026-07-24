from __future__ import annotations

from typing import Any, assert_never

from fastapi import HTTPException
from fastapi import status as http_status

from src.api.order_requests.domain import (
    OrderRequestAccessDenied,
    OrderRequestCannotAccept,
    OrderRequestCardListingNotFound,
    OrderRequestInvalidQuantities,
    OrderRequestInvalidTransition,
    OrderRequestItemAlreadyExists,
    OrderRequestItemCannotBeAdded,
    OrderRequestItemCannotBeRestored,
    OrderRequestItemNotFound,
    OrderRequestNotEditable,
    OrderRequestNotFound,
)
from src.core.schema import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)

_UNAUTHORIZED_RESPONSE = UNAUTHORIZED_RESPONSE
_FORBIDDEN_RESPONSE = FORBIDDEN_RESPONSE
_REQUEST_NOT_FOUND_RESPONSE = {
    **NOT_FOUND_RESPONSE,
    "description": "La Orden no existe o pertenece a otro Usuario.",
}
_CONFLICT_RESPONSE = {
    **CONFLICT_RESPONSE,
    "description": "La transición o sus precondiciones no son válidas.",
}
_ACCEPT_CONFLICT_RESPONSE = {
    **_CONFLICT_RESPONSE,
    "content": {
        "application/json": {
            "examples": {
                "invalidTransition": {
                    "summary": "Transición no permitida",
                    "value": {
                        "detail": (
                            "La transición solicitada no es válida para el estado "
                            "actual"
                        )
                    },
                },
                "incompletePrices": {
                    "summary": "Precios incompletos",
                    "value": {
                        "detail": (
                            "Todos los ítems activos deben tener precios completos"
                        )
                    },
                },
            }
        }
    },
}
_VALIDATION_RESPONSE = VALIDATION_RESPONSE
CREATE_ORDER_REQUEST_RESPONSES: dict[int, dict[str, Any]] = {
    401: _UNAUTHORIZED_RESPONSE,
    403: _FORBIDDEN_RESPONSE,
    404: {
        **NOT_FOUND_RESPONSE,
        "description": "El Pedido o una publicación de carta no existe.",
        "content": {
            "application/json": {
                "examples": {
                    "period": {
                        "summary": "Pedido inexistente",
                        "value": {"detail": "El Pedido no existe"},
                    },
                    "listing": {
                        "summary": "Publicación inexistente",
                        "value": {"detail": "La publicación de carta no existe"},
                    },
                }
            }
        },
    },
    409: {
        **CONFLICT_RESPONSE,
        "description": "El Pedido no está abierto para recibir Órdenes.",
        "content": {
            "application/json": {
                "example": {"detail": "El Pedido no está abierto para recibir Órdenes"}
            }
        },
    },
    422: _VALIDATION_RESPONSE,
}
ORDER_ACTION_RESPONSES: dict[int, dict[str, Any]] = {
    401: _UNAUTHORIZED_RESPONSE,
    403: _FORBIDDEN_RESPONSE,
    404: _REQUEST_NOT_FOUND_RESPONSE,
    409: _CONFLICT_RESPONSE,
    422: _VALIDATION_RESPONSE,
}
ADD_ITEM_RESPONSES: dict[int, dict[str, Any]] = {
    **ORDER_ACTION_RESPONSES,
    404: {
        **NOT_FOUND_RESPONSE,
        "description": "La Orden o la publicación de carta no existe o no es visible.",
    },
}
ITEM_ACTION_RESPONSES: dict[int, dict[str, Any]] = {
    **ORDER_ACTION_RESPONSES,
    404: {
        **NOT_FOUND_RESPONSE,
        "description": "La Orden o su ítem no existe o no es visible.",
    },
}
ACCEPT_ORDER_REQUEST_RESPONSES: dict[int, dict[str, Any]] = {
    **ORDER_ACTION_RESPONSES,
    409: _ACCEPT_CONFLICT_RESPONSE,
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
