from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deliveries.application import cases
from src.api.deliveries.domain import (
    DeliveryAccessDenied,
    DeliveryConflict,
    DeliveryEventCreate,
    DeliveryInvalidAllocation,
    DeliveryMissingFields,
    DeliveryNotFound,
    DeliveryPreferenceResponse,
    DeliveryPreferenceUpdate,
    DeliveryStageCreate,
    DeliveryStageNotFound,
    DeliveryStageResponse,
    DeliveryStageScope,
    DeliveryStageUpdate,
    FulfillmentCreate,
    FulfillmentResponse,
    InternationalShipmentCreate,
    InternationalShipmentResponse,
    InternationalShipmentUpdate,
    OrderTrackingResponse,
)
from src.api.order_requests.domain import OrderRequestResponse
from src.api.roles.domain import Actor
from src.api.roles.infrastructure.auth import get_current_user
from src.core import Err
from src.core.db import get_db

deliveries_router = APIRouter(tags=["deliveries"])
order_deliveries_router = APIRouter(tags=["deliveries"])
delivery_stages_router = APIRouter(tags=["delivery-stages"])

PositiveId = Annotated[int, Path(gt=0)]

_CONFLICT_MESSAGES = {
    "invalid_payment_transition": "El estado actual no permite cambiar el pago",
    "purchase_exists": "No se puede revertir el pago después de registrar una compra",
    "stage_key_exists": "Ya existe una etapa con esa clave y ámbito",
    "different_order_period": "Todas las Órdenes deben pertenecer al mismo Pedido",
    "order_not_paid": "La Orden debe estar pagada",
    "purchasing_finalized": "La compra de la Orden ya está cerrada",
    "item_not_active": "El ítem no está activo en la Orden",
    "quantity_above_remaining": "La cantidad supera lo pendiente del ítem",
    "nothing_to_allocate": "No quedan cantidades para asignar",
    "backward_stage_requires_correction": "Un retroceso requiere indicar el evento corregido y el motivo",
    "correction_event_not_found": "El evento corregido no pertenece a este seguimiento",
    "no_purchased_items": "Debe existir al menos una unidad comprada",
    "fulfillment_exists": "La Orden ya tiene un proceso final de entrega",
    "delivery_preference_missing": "El usuario debe elegir retiro o envío nacional",
    "order_not_organized": "La Orden todavía no está organizada",
    "pickup_has_shipping_fields": "El retiro personal no admite datos de envío nacional",
    "refresh_cooldown": "La guía se consultó recientemente; espera antes de solicitar otra actualización",
}


def _raise(error: object) -> NoReturn:
    match error:
        case DeliveryAccessDenied():
            raise HTTPException(http_status.HTTP_403_FORBIDDEN, "No tienes permiso")
        case DeliveryNotFound():
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "El recurso no existe")
        case DeliveryMissingFields(fields=fields):
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                {"message": "Faltan datos para crear el envío", "fields": list(fields)},
            )
        case DeliveryStageNotFound():
            raise HTTPException(
                http_status.HTTP_409_CONFLICT, "La etapa no existe o está inactiva"
            )
        case DeliveryInvalidAllocation(reason=reason) | DeliveryConflict(reason=reason):
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                _CONFLICT_MESSAGES.get(
                    reason, "La operación entra en conflicto con el estado actual"
                ),
            )
        case _:
            raise RuntimeError(f"Error de deliveries no manejado: {error!r}")


@order_deliveries_router.post(
    "/{order_request_id}/mark-paid",
    response_model=OrderRequestResponse,
    operation_id="markOrderRequestPaid",
    summary="Confirmar el pago de una Orden",
    description="Marca una Orden aceptada como pagada mediante una acción administrativa.",
)
async def mark_paid(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
) -> OrderRequestResponse:
    result = await cases.mark_paid(db, actor, order_request_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@order_deliveries_router.post(
    "/{order_request_id}/revert-payment",
    response_model=OrderRequestResponse,
    operation_id="revertOrderRequestPayment",
    summary="Revertir el pago de una Orden",
    description="Revierte el pago mientras no exista ninguna cantidad comprada.",
)
async def revert_payment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
) -> OrderRequestResponse:
    result = await cases.revert_payment(db, actor, order_request_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@order_deliveries_router.post(
    "/{order_request_id}/purchasing/finalize",
    response_model=OrderTrackingResponse,
    operation_id="finalizeOrderRequestPurchasing",
    summary="Cerrar la compra de una Orden",
    description="Indica que no se comprarán más cantidades de la Orden.",
)
async def finalize_purchasing(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
) -> OrderTrackingResponse:
    result = await cases.finalize_purchasing(db, actor, order_request_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@order_deliveries_router.post(
    "/{order_request_id}/purchasing/reopen",
    response_model=OrderTrackingResponse,
    operation_id="reopenOrderRequestPurchasing",
    summary="Reabrir la compra de una Orden",
    description="Permite nuevas asignaciones antes de crear la entrega final.",
)
async def reopen_purchasing(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
) -> OrderTrackingResponse:
    result = await cases.reopen_purchasing(db, actor, order_request_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@order_deliveries_router.put(
    "/{order_request_id}/delivery-preference",
    response_model=DeliveryPreferenceResponse,
    operation_id="setOrderRequestDeliveryPreference",
    summary="Elegir retiro o envío nacional",
    description="Guarda la modalidad final y valida que la dirección pertenezca al usuario.",
)
async def set_preference(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
    data: DeliveryPreferenceUpdate,
) -> DeliveryPreferenceResponse:
    result = await cases.set_preference(db, actor, order_request_id, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@order_deliveries_router.get(
    "/{order_request_id}/tracking",
    response_model=OrderTrackingResponse,
    operation_id="getOrderRequestTracking",
    summary="Consultar el seguimiento de una Orden",
    description="Devuelve pago, cantidades, envíos relacionados y entrega final.",
)
async def get_tracking(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
) -> OrderTrackingResponse:
    result = await cases.get_tracking(db, actor, order_request_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.post(
    "/international-shipments",
    status_code=http_status.HTTP_201_CREATED,
    response_model=InternationalShipmentResponse,
    operation_id="createInternationalShipment",
    summary="Crear un envío internacional",
    description="Agrupa cantidades de una o varias Órdenes pagadas del mismo Pedido.",
)
async def create_international_shipment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    data: InternationalShipmentCreate,
) -> InternationalShipmentResponse:
    result = await cases.create_international_shipment(db, actor, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.get(
    "/international-shipments",
    response_model=list[InternationalShipmentResponse],
    operation_id="listInternationalShipments",
    summary="Listar envíos internacionales",
    description="Devuelve los envíos administrativos de un Pedido.",
)
async def list_international_shipments(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_period_id: Annotated[int, Query(alias="orderPeriodId", gt=0)],
) -> list[InternationalShipmentResponse]:
    result = await cases.list_international_shipments(db, actor, order_period_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.get(
    "/international-shipments/{shipment_id}",
    response_model=InternationalShipmentResponse,
    operation_id="getInternationalShipment",
    summary="Consultar un envío internacional",
    description="Muestra cantidades y eventos sin exponer otras Órdenes al usuario.",
)
async def get_international_shipment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    shipment_id: PositiveId,
) -> InternationalShipmentResponse:
    result = await cases.get_international_shipment(db, actor, shipment_id)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.patch(
    "/international-shipments/{shipment_id}",
    response_model=InternationalShipmentResponse,
    operation_id="updateInternationalShipment",
    summary="Actualizar un envío internacional",
    description="Cambia el nombre y las referencias administrativas del envío.",
)
async def update_international_shipment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    shipment_id: PositiveId,
    data: InternationalShipmentUpdate,
) -> InternationalShipmentResponse:
    result = await cases.update_international_shipment(db, actor, shipment_id, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.post(
    "/international-shipments/{shipment_id}/events",
    response_model=InternationalShipmentResponse,
    operation_id="addInternationalShipmentEvent",
    summary="Registrar una etapa internacional",
    description="Añade un evento inmutable y permite correcciones con motivo.",
)
async def add_international_event(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    shipment_id: PositiveId,
    data: DeliveryEventCreate,
) -> InternationalShipmentResponse:
    result = await cases.add_shipment_event(db, actor, shipment_id, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.post(
    "/order-requests/{order_request_id}/fulfillments",
    status_code=http_status.HTTP_201_CREATED,
    response_model=FulfillmentResponse,
    operation_id="createOrderRequestFulfillment",
    summary="Crear la entrega final de una Orden",
    description="Prepara el retiro o crea un envío nacional con datos copiados.",
)
async def create_fulfillment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    order_request_id: PositiveId,
    data: FulfillmentCreate,
) -> FulfillmentResponse:
    result = await cases.create_fulfillment(db, actor, order_request_id, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.post(
    "/fulfillments/{fulfillment_id}/events",
    response_model=FulfillmentResponse,
    operation_id="addFulfillmentEvent",
    summary="Registrar una etapa de entrega final",
    description="Actualiza un retiro o envío nacional sin borrar su historial.",
)
async def add_fulfillment_event(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    fulfillment_id: PositiveId,
    data: DeliveryEventCreate,
) -> FulfillmentResponse:
    result = await cases.add_fulfillment_event(db, actor, fulfillment_id, data)

    if isinstance(result, Err):
        _raise(result.error)

    return result.value


@deliveries_router.post(
    "/national-shipments/{shipment_id}/refresh",
    status_code=http_status.HTTP_202_ACCEPTED,
    response_model=None,
    operation_id="requestNationalShipmentRefresh",
    summary="Solicitar la actualización de una guía",
    description="Marca la guía para que el proceso periódico la consulte pronto.",
)
async def refresh_national_shipment(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    shipment_id: PositiveId,
) -> Response:
    result = await cases.request_refresh(db, actor, shipment_id)
    if isinstance(result, Err):
        _raise(result.error)
    return Response(status_code=http_status.HTTP_202_ACCEPTED)


@delivery_stages_router.get(
    "",
    response_model=list[DeliveryStageResponse],
    operation_id="listDeliveryStages",
    summary="Listar etapas de entrega",
    description="Devuelve el catálogo ordenado y permite filtrar por ámbito.",
)
async def list_delivery_stages(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    scope: DeliveryStageScope | None = None,
) -> list[DeliveryStageResponse]:
    result = await cases.list_stages(db, actor, scope)
    if isinstance(result, Err):
        _raise(result.error)
    return result.value


@delivery_stages_router.post(
    "",
    status_code=http_status.HTTP_201_CREATED,
    response_model=DeliveryStageResponse,
    operation_id="createDeliveryStage",
    summary="Crear una etapa de entrega",
    description="Añade una clave estable al catálogo logístico.",
)
async def create_delivery_stage(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    data: DeliveryStageCreate,
) -> DeliveryStageResponse:
    result = await cases.create_stage(db, actor, data)
    if isinstance(result, Err):
        _raise(result.error)
    return result.value


@delivery_stages_router.patch(
    "/{stage_id}",
    response_model=DeliveryStageResponse,
    operation_id="updateDeliveryStage",
    summary="Actualizar una etapa de entrega",
    description="Cambia nombre, orden, tipo o disponibilidad sin cambiar su clave.",
)
async def update_delivery_stage(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    stage_id: PositiveId,
    data: DeliveryStageUpdate,
) -> DeliveryStageResponse:
    result = await cases.update_stage(db, actor, stage_id, data)
    if isinstance(result, Err):
        _raise(result.error)
    return result.value
