from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from src.api.deliveries.domain import (
    DeliveryAccessDenied,
    DeliveryConflict,
    DeliveryEventCreate,
    DeliveryEventResponse,
    DeliveryEventSource,
    DeliveryInvalidAllocation,
    DeliveryMethod,
    DeliveryMissingFields,
    DeliveryNotFound,
    DeliveryPreferenceResponse,
    DeliveryPreferenceUpdate,
    DeliveryStageCreate,
    DeliveryStageKind,
    DeliveryStageNotFound,
    DeliveryStageResponse,
    DeliveryStageScope,
    DeliveryStageUpdate,
    FulfillmentCreate,
    FulfillmentResponse,
    InternationalShipmentCreate,
    InternationalShipmentResponse,
    InternationalShipmentUpdate,
    InternationalTrackingSummary,
    NationalCarrier,
    OrderTrackingResponse,
    ShipmentAllocationResponse,
    ShipmentKind,
    TrackingItemResponse,
)
from src.api.deliveries.repository import (
    DeliveryEvent,
    DeliveryPreference,
    DeliveryShipment,
    DeliveryShipmentAllocation,
    DeliveryStage,
    dao_delivery_fulfillments,
    dao_delivery_preferences,
    dao_delivery_shipments,
    dao_delivery_stages,
)
from src.api.order_requests.domain import (
    OrderRequestEventType,
    OrderRequestResponse,
    OrderRequestStatus,
)
from src.api.order_requests.repository import (
    dao_order_request_histories,
    dao_order_requests,
)
from src.api.roles.domain import Actor, PermissionCode
from src.api.users.repository import dao_user_addresses, dao_users
from src.core import Err, Ok, Result
from src.core.db import DAOError
from src.core.utils.utils import Empty, datetime_now
from src.settings.delivery_settings import delivery_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.deliveries.repository import DeliveryFulfillment
    from src.api.order_requests.repository import OrderRequest, OrderRequestItem


type DeliveryError = (
    DeliveryAccessDenied
    | DeliveryNotFound
    | DeliveryConflict
    | DeliveryStageNotFound
    | DeliveryInvalidAllocation
    | DeliveryMissingFields
)


def _has(actor: Actor, permission: PermissionCode) -> bool:
    return permission in actor.permissions


def _stage_response(stage: DeliveryStage) -> DeliveryStageResponse:
    return DeliveryStageResponse.model_validate(stage)


def _order_response(request: OrderRequest) -> OrderRequestResponse:
    response = OrderRequestResponse.model_validate(request)
    response.items = [item for item in response.items if item.removed_at is None]
    return response


def _event_response(event: DeliveryEvent) -> DeliveryEventResponse:
    return DeliveryEventResponse.model_validate(event)


def _shipment_response(
    shipment: DeliveryShipment,
    *,
    visible_order_request_ids: set[int] | None = None,
) -> InternationalShipmentResponse:
    allocations = shipment.allocations

    if visible_order_request_ids is not None:
        allocations = [
            allocation
            for allocation in allocations
            if allocation.order_request_id in visible_order_request_ids
        ]

    return InternationalShipmentResponse(
        id=shipment.id,
        order_period_id=cast(int, shipment.order_period_id),
        name=shipment.name,
        reference=shipment.reference,
        external_references=shipment.external_references,
        current_stage=_stage_response(shipment.current_stage),
        allocations=[
            ShipmentAllocationResponse.model_validate(allocation)
            for allocation in allocations
        ],
        events=[
            _event_response(event)
            for event in sorted(shipment.events, key=lambda item: item.occurred_at)
        ],
        date_added=shipment.date_added,
        date_updated=shipment.date_updated,
    )


def _preference_response(preference: DeliveryPreference) -> DeliveryPreferenceResponse:
    return DeliveryPreferenceResponse.model_validate(preference)


def _fulfillment_response(fulfillment: DeliveryFulfillment) -> FulfillmentResponse:
    shipment = fulfillment.shipment
    events = shipment.events if shipment is not None else fulfillment.events

    return FulfillmentResponse(
        id=fulfillment.id,
        order_request_id=fulfillment.order_request_id,
        method=DeliveryMethod(fulfillment.method),
        current_stage=_stage_response(fulfillment.current_stage),
        carrier=NationalCarrier(shipment.carrier)
        if shipment and shipment.carrier
        else None,
        tracking_number=shipment.tracking_number if shipment else None,
        shipping_cost=fulfillment.shipping_cost,
        currency=fulfillment.currency,
        cost_payer=fulfillment.cost_payer,
        recipient_snapshot=fulfillment.recipient_snapshot,
        address_snapshot=fulfillment.address_snapshot,
        last_checked_at=shipment.last_checked_at if shipment else None,
        next_check_at=shipment.next_check_at if shipment else None,
        has_tracking_error=bool(shipment and shipment.last_error),
        needs_review=shipment.needs_review if shipment else False,
        events=[
            _event_response(event)
            for event in sorted(events, key=lambda item: item.occurred_at)
        ],
        date_added=fulfillment.date_added,
        date_updated=fulfillment.date_updated,
    )


async def _request_or_error(
    db: AsyncSession, order_request_id: int, *, lock: bool = False
) -> OrderRequest | DeliveryNotFound:
    request = (
        await dao_order_requests.get_for_update(db, order_request_id)
        if lock
        else await dao_order_requests.get(db, order_request_id)
    )

    if request is Empty:
        return DeliveryNotFound("order_request", order_request_id)

    return cast("OrderRequest", request)


async def mark_paid(
    db: AsyncSession, actor: Actor, order_request_id: int
) -> Result[OrderRequestResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE_PAYMENTS):
        return Err(DeliveryAccessDenied())

    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    current = OrderRequestStatus(request.status)

    if current is not OrderRequestStatus.ACCEPTED:
        return Err(DeliveryConflict("invalid_payment_transition"))

    now = datetime_now()
    request.status = OrderRequestStatus.PAID
    request.paid_at = now
    request.paid_by_user_id = actor.user_id

    try:
        await dao_order_requests.flush(db)
        await dao_order_request_histories.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.STATUS_CHANGED,
            actor_user_id=actor.user_id,
            occurred_at=now,
            changes=[
                {"field": "status", "oldValue": "accepted", "newValue": "paid"},
                {"field": "paidAt", "oldValue": None, "newValue": now.isoformat()},
                {"field": "paidByUserId", "oldValue": None, "newValue": actor.user_id},
            ],
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise
    return Ok(_order_response(request))


async def revert_payment(
    db: AsyncSession, actor: Actor, order_request_id: int
) -> Result[OrderRequestResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE_PAYMENTS):
        return Err(DeliveryAccessDenied())

    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    if OrderRequestStatus(request.status) is not OrderRequestStatus.PAID:
        return Err(DeliveryConflict("invalid_payment_transition"))

    totals = await dao_delivery_shipments.allocated_by_item(
        db, [item.id for item in request.items]
    )

    if any(totals.values()):
        return Err(DeliveryConflict("purchase_exists"))

    old_paid_at = request.paid_at
    old_paid_by = request.paid_by_user_id
    request.status = OrderRequestStatus.ACCEPTED
    request.paid_at = None
    request.paid_by_user_id = None

    try:
        await dao_order_requests.flush(db)
        await dao_order_request_histories.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.STATUS_CHANGED,
            actor_user_id=actor.user_id,
            changes=[
                {"field": "status", "oldValue": "paid", "newValue": "accepted"},
                {
                    "field": "paidAt",
                    "oldValue": old_paid_at.isoformat() if old_paid_at else None,
                    "newValue": None,
                },
                {"field": "paidByUserId", "oldValue": old_paid_by, "newValue": None},
            ],
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(_order_response(request))


async def list_stages(
    db: AsyncSession, actor: Actor, scope: DeliveryStageScope | None
) -> Result[list[DeliveryStageResponse], DeliveryAccessDenied]:
    if not actor.permissions.intersection(
        {PermissionCode.DELIVERIES_READ_SELF, PermissionCode.DELIVERIES_READ_ANY}
    ):
        return Err(DeliveryAccessDenied())

    stages = await dao_delivery_stages.list_for_scope(
        db, scope.value if scope else None
    )

    return Ok([_stage_response(stage) for stage in stages])


async def create_stage(
    db: AsyncSession, actor: Actor, data: DeliveryStageCreate
) -> Result[DeliveryStageResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERY_STAGES_MANAGE):
        return Err(DeliveryAccessDenied())

    existing = await dao_delivery_stages.get_by_key(
        db, scope=data.scope.value, key=data.key
    )

    if existing is not Empty:
        return Err(DeliveryConflict("stage_key_exists"))

    stage = DeliveryStage(**data.model_dump(mode="python"))
    await dao_delivery_stages.add(db, stage)
    await db.commit()

    return Ok(_stage_response(stage))


async def update_stage(
    db: AsyncSession, actor: Actor, stage_id: int, data: DeliveryStageUpdate
) -> Result[DeliveryStageResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERY_STAGES_MANAGE):
        return Err(DeliveryAccessDenied())

    stage = await dao_delivery_stages.get_for_update(db, stage_id)

    if stage is Empty:
        return Err(DeliveryNotFound("stage", stage_id))

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)

    await dao_delivery_stages.flush(db)
    await db.commit()

    return Ok(_stage_response(stage))


async def create_international_shipment(
    db: AsyncSession, actor: Actor, data: InternationalShipmentCreate
) -> Result[InternationalShipmentResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    stage = await dao_delivery_stages.get_by_key(
        db,
        scope=DeliveryStageScope.INTERNATIONAL.value,
        key="purchase_confirmed",
        active_only=True,
    )

    if stage is Empty:
        return Err(DeliveryStageNotFound("international", "purchase_confirmed"))

    requests: list[OrderRequest] = []
    planned: list[tuple[OrderRequest, OrderRequestItem, int]] = []

    for requested in sorted(data.allocations, key=lambda item: item.order_request_id):
        request = await _request_or_error(db, requested.order_request_id, lock=True)

        if isinstance(request, DeliveryNotFound):
            return Err(request)

        if request.order_period_id != data.order_period_id:
            return Err(DeliveryInvalidAllocation("different_order_period"))

        if OrderRequestStatus(request.status) is not OrderRequestStatus.PAID:
            return Err(DeliveryInvalidAllocation("order_not_paid"))

        if request.purchasing_finalized_at is not None:
            return Err(DeliveryInvalidAllocation("purchasing_finalized"))

        active = {item.id: item for item in request.items if item.removed_at is None}
        totals = await dao_delivery_shipments.allocated_by_item(db, list(active))
        selections = requested.items

        if selections is None:
            quantities = [
                (item, item.agreed_quantity - totals.get(item.id, 0))
                for item in active.values()
            ]
            quantities = [
                (item, quantity) for item, quantity in quantities if quantity > 0
            ]
        else:
            quantities = []

            for selected in selections:
                item = active.get(selected.order_request_item_id)

                if item is None:
                    return Err(DeliveryInvalidAllocation("item_not_active"))

                remaining = item.agreed_quantity - totals.get(item.id, 0)

                if selected.quantity > remaining:
                    return Err(DeliveryInvalidAllocation("quantity_above_remaining"))

                quantities.append((item, selected.quantity))

        if not quantities:
            return Err(DeliveryInvalidAllocation("nothing_to_allocate"))

        requests.append(request)
        planned.extend((request, item, quantity) for item, quantity in quantities)

    shipment = DeliveryShipment(
        kind=ShipmentKind.INTERNATIONAL.value,
        order_period_id=data.order_period_id,
        name=data.name,
        reference=data.reference,
        external_references=data.external_references,
        current_stage_id=stage.id,
    )
    shipment.current_stage = stage
    now = datetime_now()

    try:
        await dao_delivery_shipments.add(db, shipment)

        for request, item, quantity in planned:
            allocation = DeliveryShipmentAllocation(
                shipment_id=shipment.id,
                order_request_id=request.id,
                order_request_item_id=item.id,
                quantity=quantity,
            )
            db.add(allocation)

        event = DeliveryEvent(
            shipment_id=shipment.id,
            source=DeliveryEventSource.ADMIN.value,
            actor_user_id=actor.user_id,
            occurred_at=now,
            stage_id=stage.id,
            stage_key=stage.key,
            stage_name=stage.name,
        )
        db.add(event)
        await db.flush()

        for request in requests:
            totals = await dao_delivery_shipments.allocated_by_item(
                db, [item.id for item in request.items if item.removed_at is None]
            )
            complete = all(
                totals.get(item.id, 0) == item.agreed_quantity
                for item in request.items
                if item.removed_at is None
            )

            if complete:
                request.purchasing_finalized_at = now
                request.purchasing_finalized_by_user_id = actor.user_id
                await dao_order_request_histories.create(
                    db,
                    order_request_id=request.id,
                    event=OrderRequestEventType.UPDATED,
                    actor_user_id=actor.user_id,
                    changes=[
                        {
                            "field": "purchasingFinalizedAt",
                            "oldValue": None,
                            "newValue": now.isoformat(),
                        }
                    ],
                )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    created = await dao_delivery_shipments.get_full(db, shipment.id)

    if created is Empty:
        raise RuntimeError("El envío creado no pudo recuperarse")

    return Ok(_shipment_response(created))


async def list_international_shipments(
    db: AsyncSession, actor: Actor, order_period_id: int
) -> Result[list[InternationalShipmentResponse], DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_READ_ANY):
        return Err(DeliveryAccessDenied())

    shipments = await dao_delivery_shipments.list_international(db, order_period_id)

    return Ok([_shipment_response(shipment) for shipment in shipments])


async def get_international_shipment(
    db: AsyncSession, actor: Actor, shipment_id: int
) -> Result[InternationalShipmentResponse, DeliveryError]:
    shipment = await dao_delivery_shipments.get_full(db, shipment_id)

    if shipment is Empty or shipment.kind != ShipmentKind.INTERNATIONAL.value:
        return Err(DeliveryNotFound("shipment", shipment_id))

    if _has(actor, PermissionCode.DELIVERIES_READ_ANY):
        return Ok(_shipment_response(shipment))

    if not _has(actor, PermissionCode.DELIVERIES_READ_SELF):
        return Err(DeliveryAccessDenied())

    owner_ids: set[int] = set()
    visible_request_ids: set[int] = set()

    for allocation in shipment.allocations:
        request = await dao_order_requests.get(db, allocation.order_request_id)

        if request is not Empty:
            owner_ids.add(request.created_by_user_id)
            if request.created_by_user_id == actor.user_id:
                visible_request_ids.add(request.id)

    if actor.user_id not in owner_ids:
        return Err(DeliveryNotFound("shipment", shipment_id))

    return Ok(
        _shipment_response(
            shipment,
            visible_order_request_ids=visible_request_ids,
        )
    )


async def update_international_shipment(
    db: AsyncSession,
    actor: Actor,
    shipment_id: int,
    data: InternationalShipmentUpdate,
) -> Result[InternationalShipmentResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    shipment = await dao_delivery_shipments.get_full(db, shipment_id, for_update=True)

    if shipment is Empty or shipment.kind != ShipmentKind.INTERNATIONAL.value:
        return Err(DeliveryNotFound("shipment", shipment_id))

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)

    await dao_delivery_shipments.flush(db)
    await db.commit()

    return Ok(_shipment_response(shipment))


async def add_shipment_event(
    db: AsyncSession, actor: Actor, shipment_id: int, data: DeliveryEventCreate
) -> Result[InternationalShipmentResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    shipment = await dao_delivery_shipments.get_full(db, shipment_id, for_update=True)

    if shipment is Empty or shipment.kind != ShipmentKind.INTERNATIONAL.value:
        return Err(DeliveryNotFound("shipment", shipment_id))

    stage = await dao_delivery_stages.get_by_key(
        db,
        scope=DeliveryStageScope.INTERNATIONAL.value,
        key=data.stage_key,
        active_only=True,
    )

    if stage is Empty:
        return Err(DeliveryStageNotFound("international", data.stage_key))

    current = shipment.current_stage
    backward = (
        stage.kind == DeliveryStageKind.PROGRESS.value
        and current.kind == DeliveryStageKind.PROGRESS.value
        and stage.position < current.position
    )

    if backward and data.correction_of_event_id is None:
        return Err(DeliveryConflict("backward_stage_requires_correction"))

    if data.correction_of_event_id is not None and not any(
        event.id == data.correction_of_event_id for event in shipment.events
    ):
        return Err(DeliveryConflict("correction_event_not_found"))

    event = DeliveryEvent(
        shipment_id=shipment.id,
        source=DeliveryEventSource.ADMIN.value,
        actor_user_id=actor.user_id,
        occurred_at=data.occurred_at or datetime_now(),
        stage_id=stage.id,
        stage_key=stage.key,
        stage_name=stage.name,
        note=data.note,
        correction_of_event_id=data.correction_of_event_id,
        correction_reason=data.correction_reason,
    )
    shipment.current_stage_id = stage.id
    shipment.current_stage = stage
    db.add(event)
    await db.flush()
    shipment.events.append(event)
    await db.commit()

    return Ok(_shipment_response(shipment))


async def finalize_purchasing(
    db: AsyncSession, actor: Actor, order_request_id: int
) -> Result[OrderTrackingResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    if OrderRequestStatus(request.status) is not OrderRequestStatus.PAID:
        return Err(DeliveryConflict("order_not_paid"))

    totals = await dao_delivery_shipments.allocated_by_item(
        db, [item.id for item in request.items if item.removed_at is None]
    )

    if not any(totals.values()):
        return Err(DeliveryConflict("no_purchased_items"))

    if request.purchasing_finalized_at is None:
        now = datetime_now()
        request.purchasing_finalized_at = now
        request.purchasing_finalized_by_user_id = actor.user_id
        await dao_order_requests.flush(db)
        await dao_order_request_histories.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.UPDATED,
            actor_user_id=actor.user_id,
            changes=[
                {
                    "field": "purchasingFinalizedAt",
                    "oldValue": None,
                    "newValue": now.isoformat(),
                }
            ],
        )
        await db.commit()

    return await get_tracking(db, actor, order_request_id)


async def reopen_purchasing(
    db: AsyncSession, actor: Actor, order_request_id: int
) -> Result[OrderTrackingResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    fulfillment = await dao_delivery_fulfillments.get_for_order(db, request.id)

    if fulfillment is not Empty:
        return Err(DeliveryConflict("fulfillment_exists"))

    if request.purchasing_finalized_at is not None:
        old = request.purchasing_finalized_at
        request.purchasing_finalized_at = None
        request.purchasing_finalized_by_user_id = None
        await dao_order_requests.flush(db)
        await dao_order_request_histories.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.UPDATED,
            actor_user_id=actor.user_id,
            changes=[
                {
                    "field": "purchasingFinalizedAt",
                    "oldValue": old.isoformat(),
                    "newValue": None,
                }
            ],
        )
        await db.commit()

    return await get_tracking(db, actor, order_request_id)


async def set_preference(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    data: DeliveryPreferenceUpdate,
) -> Result[DeliveryPreferenceResponse, DeliveryError]:
    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    can_select = (
        actor.user_id == request.created_by_user_id
        and _has(actor, PermissionCode.DELIVERIES_SELECT_SELF)
    ) or _has(actor, PermissionCode.DELIVERIES_MANAGE)

    if not can_select:
        return Err(DeliveryAccessDenied())

    if OrderRequestStatus(request.status) is not OrderRequestStatus.PAID:
        return Err(DeliveryConflict("order_not_paid"))

    if await dao_delivery_fulfillments.get_for_order(db, request.id) is not Empty:
        return Err(DeliveryConflict("fulfillment_exists"))

    if data.user_address_id is not None:
        address = await dao_user_addresses.get(db, data.user_address_id)

        if address is Empty or address.user_id != request.created_by_user_id:
            return Err(DeliveryNotFound("user_address", data.user_address_id))

    preference = await dao_delivery_preferences.get_for_order(db, request.id)

    if preference is Empty:
        preference = DeliveryPreference(
            order_request_id=request.id,
            method=data.method.value,
            user_address_id=data.user_address_id,
        )
        await dao_delivery_preferences.add(db, preference)
    else:
        preference.method = data.method.value
        preference.user_address_id = data.user_address_id
        await dao_delivery_preferences.flush(db)
    await db.commit()

    return Ok(_preference_response(preference))


async def _is_organized(db: AsyncSession, request: OrderRequest) -> bool:
    if request.purchasing_finalized_at is None:
        return False

    shipments = await dao_delivery_shipments.list_for_order(db, request.id)

    return bool(shipments) and all(
        shipment.current_stage.key == "organized" for shipment in shipments
    )


async def create_fulfillment(
    db: AsyncSession, actor: Actor, order_request_id: int, data: FulfillmentCreate
) -> Result[FulfillmentResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    request = await _request_or_error(db, order_request_id, lock=True)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    if OrderRequestStatus(request.status) is not OrderRequestStatus.PAID:
        return Err(DeliveryConflict("order_not_paid"))

    if not await _is_organized(db, request):
        return Err(DeliveryConflict("order_not_organized"))

    if await dao_delivery_fulfillments.get_for_order(db, request.id) is not Empty:
        return Err(DeliveryConflict("fulfillment_exists"))

    preference = await dao_delivery_preferences.get_for_order(db, request.id)

    if preference is Empty:
        return Err(DeliveryConflict("delivery_preference_missing"))

    method = DeliveryMethod(preference.method)
    scope = (
        DeliveryStageScope.PICKUP
        if method is DeliveryMethod.PICKUP
        else DeliveryStageScope.NATIONAL
    )
    first_key = "ready_for_pickup" if method is DeliveryMethod.PICKUP else "preparing"
    stage = await dao_delivery_stages.get_by_key(
        db, scope=scope.value, key=first_key, active_only=True
    )

    if stage is Empty:
        return Err(DeliveryStageNotFound(scope.value, first_key))

    recipient = None
    address_snapshot = None

    if method is DeliveryMethod.NATIONAL_SHIPPING:
        missing = []

        if data.carrier is None:
            missing.append("carrier")

        if data.tracking_number is None:
            missing.append("trackingNumber")

        user = await dao_users.get(db, request.created_by_user_id)
        address = (
            await dao_user_addresses.get(db, preference.user_address_id)
            if preference.user_address_id is not None
            else Empty
        )

        if user is Empty or not user.name:
            missing.append("name")

        if user is Empty or not user.phone_number:
            missing.append("phoneNumber")

        if address is Empty:
            missing.append("userAddressId")

        if data.shipping_cost is not None and data.cost_payer is None:
            missing.append("costPayer")

        if missing:
            return Err(DeliveryMissingFields(tuple(missing)))

        recipient = {
            "name": user.name,
            "phoneCode": user.phone_code,
            "phoneNumber": user.phone_number,
            "idNumber": user.id_number,
        }
        address_snapshot = {
            "sourceAddressId": address.id,
            "name": address.name,
            "state": address.state,
            "city": address.city,
            "address": address.address,
            "address2": address.address_2,
            "zipCode": address.zip_code,
            "latitude": float(address.latitude)
            if address.latitude is not None
            else None,
            "longitude": float(address.longitude)
            if address.longitude is not None
            else None,
        }
    elif any((data.carrier, data.tracking_number, data.shipping_cost, data.cost_payer)):
        return Err(DeliveryConflict("pickup_has_shipping_fields"))

    from src.api.deliveries.repository import DeliveryFulfillment

    fulfillment = DeliveryFulfillment(
        order_request_id=request.id,
        method=method.value,
        current_stage_id=stage.id,
        recipient_snapshot=recipient,
        address_snapshot=address_snapshot,
        shipping_cost=data.shipping_cost,
        currency=data.currency if data.shipping_cost is not None else None,
        cost_payer=data.cost_payer.value if data.cost_payer else None,
    )
    fulfillment.current_stage = stage
    now = datetime_now()

    try:
        await dao_delivery_fulfillments.add(db, fulfillment)

        if method is DeliveryMethod.NATIONAL_SHIPPING:
            shipment = DeliveryShipment(
                kind=ShipmentKind.NATIONAL.value,
                fulfillment_id=fulfillment.id,
                name=f"Envío nacional de Orden {request.id}",
                current_stage_id=stage.id,
                carrier=data.carrier.value if data.carrier else None,
                tracking_number=data.tracking_number,
                next_check_at=now,
            )
            await dao_delivery_shipments.add(db, shipment)
            event = DeliveryEvent(
                shipment_id=shipment.id,
                source=DeliveryEventSource.ADMIN.value,
                actor_user_id=actor.user_id,
                occurred_at=now,
                stage_id=stage.id,
                stage_key=stage.key,
                stage_name=stage.name,
            )
            db.add(event)
            await db.flush()
        else:
            event = DeliveryEvent(
                fulfillment_id=fulfillment.id,
                source=DeliveryEventSource.ADMIN.value,
                actor_user_id=actor.user_id,
                occurred_at=now,
                stage_id=stage.id,
                stage_key=stage.key,
                stage_name=stage.name,
            )
            db.add(event)
            await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    created = await dao_delivery_fulfillments.get_full(db, fulfillment.id)

    if created is Empty:
        raise RuntimeError("La entrega creada no pudo recuperarse")

    return Ok(_fulfillment_response(created))


async def add_fulfillment_event(
    db: AsyncSession, actor: Actor, fulfillment_id: int, data: DeliveryEventCreate
) -> Result[FulfillmentResponse, DeliveryError]:
    if not _has(actor, PermissionCode.DELIVERIES_MANAGE):
        return Err(DeliveryAccessDenied())

    fulfillment = await dao_delivery_fulfillments.get_full(
        db, fulfillment_id, for_update=True
    )

    if fulfillment is Empty:
        return Err(DeliveryNotFound("fulfillment", fulfillment_id))

    scope = (
        DeliveryStageScope.PICKUP
        if fulfillment.method == DeliveryMethod.PICKUP.value
        else DeliveryStageScope.NATIONAL
    )
    stage = await dao_delivery_stages.get_by_key(
        db, scope=scope.value, key=data.stage_key, active_only=True
    )

    if stage is Empty:
        return Err(DeliveryStageNotFound(scope.value, data.stage_key))

    current = fulfillment.current_stage
    backward = (
        stage.kind == DeliveryStageKind.PROGRESS.value
        and current.kind == DeliveryStageKind.PROGRESS.value
        and stage.position < current.position
    )
    owner_events = (
        fulfillment.shipment.events if fulfillment.shipment else fulfillment.events
    )

    if backward and data.correction_of_event_id is None:
        return Err(DeliveryConflict("backward_stage_requires_correction"))

    if data.correction_of_event_id is not None and not any(
        event.id == data.correction_of_event_id for event in owner_events
    ):
        return Err(DeliveryConflict("correction_event_not_found"))

    event = DeliveryEvent(
        shipment_id=fulfillment.shipment.id if fulfillment.shipment else None,
        fulfillment_id=None if fulfillment.shipment else fulfillment.id,
        source=DeliveryEventSource.ADMIN.value,
        actor_user_id=actor.user_id,
        occurred_at=data.occurred_at or datetime_now(),
        stage_id=stage.id,
        stage_key=stage.key,
        stage_name=stage.name,
        note=data.note,
        correction_of_event_id=data.correction_of_event_id,
        correction_reason=data.correction_reason,
    )
    fulfillment.current_stage_id = stage.id
    fulfillment.current_stage = stage

    if fulfillment.shipment:
        fulfillment.shipment.current_stage_id = stage.id
        fulfillment.shipment.current_stage = stage

        if stage.is_terminal:
            fulfillment.shipment.next_check_at = None

    db.add(event)
    await db.flush()
    owner_events.append(event)
    await db.commit()

    return Ok(_fulfillment_response(fulfillment))


async def request_refresh(
    db: AsyncSession, actor: Actor, shipment_id: int
) -> Result[None, DeliveryError]:
    shipment = await dao_delivery_shipments.get_full(db, shipment_id, for_update=True)

    if shipment is Empty or shipment.kind != ShipmentKind.NATIONAL.value:
        return Err(DeliveryNotFound("national_shipment", shipment_id))

    fulfillment = await dao_delivery_fulfillments.get_full(
        db, cast(int, shipment.fulfillment_id)
    )

    if fulfillment is Empty:
        return Err(DeliveryNotFound("fulfillment", cast(int, shipment.fulfillment_id)))

    request = await _request_or_error(db, fulfillment.order_request_id)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    allowed = _has(actor, PermissionCode.DELIVERIES_REFRESH_ANY) or (
        actor.user_id == request.created_by_user_id
        and _has(actor, PermissionCode.DELIVERIES_REFRESH_SELF)
    )

    if not allowed:
        return Err(DeliveryNotFound("national_shipment", shipment_id))

    now = datetime_now()

    if shipment.last_checked_at and now - shipment.last_checked_at < timedelta(
        seconds=delivery_settings.manual_refresh_cooldown_seconds
    ):
        return Err(DeliveryConflict("refresh_cooldown"))

    shipment.refresh_requested_at = now
    shipment.next_check_at = now
    await dao_delivery_shipments.flush(db)
    await db.commit()

    return Ok(None)


async def get_tracking(
    db: AsyncSession, actor: Actor, order_request_id: int
) -> Result[OrderTrackingResponse, DeliveryError]:
    request = await _request_or_error(db, order_request_id)

    if isinstance(request, DeliveryNotFound):
        return Err(request)

    allowed = _has(actor, PermissionCode.DELIVERIES_READ_ANY) or (
        actor.user_id == request.created_by_user_id
        and _has(actor, PermissionCode.DELIVERIES_READ_SELF)
    )

    if not allowed:
        return Err(DeliveryNotFound("order_request", order_request_id))

    active_items = [item for item in request.items if item.removed_at is None]
    totals = await dao_delivery_shipments.allocated_by_item(
        db, [item.id for item in active_items]
    )
    shipments = await dao_delivery_shipments.list_for_order(db, request.id)
    item_responses = [
        TrackingItemResponse(
            order_request_item_id=item.id,
            agreed_quantity=item.agreed_quantity,
            purchased_quantity=totals.get(item.id, 0),
            pending_quantity=max(item.agreed_quantity - totals.get(item.id, 0), 0),
        )
        for item in active_items
    ]

    if not shipments:
        stage_key, stage_name, partial = "awaiting_purchase", "Esperando compra", False
    else:
        progress = [
            shipment.current_stage
            for shipment in shipments
            if shipment.current_stage.kind == DeliveryStageKind.PROGRESS.value
        ]
        current = (
            min(progress, key=lambda stage: stage.position)
            if progress
            else shipments[0].current_stage
        )
        stage_key, stage_name = current.key, current.name
        partial = len({shipment.current_stage.key for shipment in shipments}) > 1

    if any(item.pending_quantity > 0 for item in item_responses) and totals:
        partial = True

    preference = await dao_delivery_preferences.get_for_order(db, request.id)
    fulfillment = await dao_delivery_fulfillments.get_for_order(db, request.id)

    return Ok(
        OrderTrackingResponse(
            order_request_id=request.id,
            is_paid=OrderRequestStatus(request.status) is OrderRequestStatus.PAID,
            paid_at=request.paid_at,
            items=item_responses,
            international_summary=InternationalTrackingSummary(
                stage_key=stage_key,
                stage_name=stage_name,
                is_partial=partial,
                purchasing_finalized=request.purchasing_finalized_at is not None,
            ),
            international_shipments=[
                _shipment_response(
                    item,
                    visible_order_request_ids={request.id},
                )
                for item in shipments
            ],
            preference=None
            if preference is Empty
            else _preference_response(preference),
            fulfillment=None
            if fulfillment is Empty
            else _fulfillment_response(fulfillment),
        )
    )
