from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast

from src.api.order_periods.domain import (
    OrderPeriodNotFound,
    OrderPeriodStatus,
    resolve_order_period_status,
)
from src.api.order_periods.repository import dao_order_periods as period_dao
from src.api.order_requests.domain import (
    DEFAULT_SHIPPING_PRICE,
    OrderRequestAccessDenied,
    OrderRequestCannotAccept,
    OrderRequestCardListingNotFound,
    OrderRequestCreate,
    OrderRequestEventType,
    OrderRequestHistoryResponse,
    OrderRequestInvalidQuantities,
    OrderRequestInvalidTransition,
    OrderRequestItemAlreadyExists,
    OrderRequestItemCannotBeAdded,
    OrderRequestItemCannotBeRestored,
    OrderRequestItemCreate,
    OrderRequestItemNotFound,
    OrderRequestItemPricingUpdate,
    OrderRequestItemUpdate,
    OrderRequestNotEditable,
    OrderRequestNotFound,
    OrderRequestPeriodNotOpen,
    OrderRequestPricingUpdate,
    OrderRequestResponse,
    OrderRequestStatus,
    OrderRequestUpdate,
    can_accept_order_request,
    can_access_order_request,
    can_add_order_request_item,
    can_edit_order_request,
    can_restore_order_request_item,
    can_transition_order_request,
)
from src.api.order_requests.repository import (
    dao_card_listing_references as listing_dao,
)
from src.api.order_requests.repository import dao_order_request_histories as history_dao
from src.api.order_requests.repository import dao_order_request_items as item_dao
from src.api.order_requests.repository import dao_order_requests as request_dao
from src.api.roles.domain import Actor, AuthorizationDecision, PermissionCode
from src.core import Err, Ok, Result
from src.core.db import DAOError
from src.core.utils.utils import Empty, datetime_now

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.order_periods.repository import OrderPeriod
    from src.api.order_requests.repository import CardListingSnapshot, OrderRequest


type CreateOrderRequestError = (
    OrderRequestAccessDenied
    | OrderPeriodNotFound
    | OrderRequestPeriodNotOpen
    | OrderRequestCardListingNotFound
)
type ReadOrderRequestError = OrderRequestAccessDenied | OrderRequestNotFound
type MutateOrderRequestError = (
    OrderRequestAccessDenied | OrderRequestNotFound | OrderRequestNotEditable
)
type AddOrderRequestItemError = (
    MutateOrderRequestError
    | OrderRequestItemCannotBeAdded
    | OrderRequestItemAlreadyExists
    | OrderRequestCardListingNotFound
)
type MutateOrderRequestItemError = (
    MutateOrderRequestError
    | OrderRequestItemNotFound
    | OrderRequestItemCannotBeRestored
    | OrderRequestInvalidQuantities
)
type ReviewOrderRequestError = (
    OrderRequestAccessDenied
    | OrderRequestNotFound
    | OrderRequestInvalidTransition
    | OrderRequestCannotAccept
)
type PriceOrderRequestItemError = (
    OrderRequestAccessDenied
    | OrderRequestNotFound
    | OrderRequestItemNotFound
    | OrderRequestNotEditable
)
type PriceOrderRequestError = (
    OrderRequestAccessDenied | OrderRequestNotFound | OrderRequestNotEditable
)


def _can_list(actor: Actor) -> tuple[int | None, OrderRequestAccessDenied | None]:
    if PermissionCode.ORDER_REQUESTS_READ_ANY in actor.permissions:
        return None, None

    if PermissionCode.ORDER_REQUESTS_READ_SELF in actor.permissions:
        return actor.user_id, None

    return None, OrderRequestAccessDenied()


def _change(field: str, old_value: object, new_value: object) -> dict[str, object]:
    def history_value(value: object) -> object:
        return str(value) if isinstance(value, Decimal) else value

    return {
        "field": field,
        "oldValue": history_value(old_value),
        "newValue": history_value(new_value),
    }


def _response(request: OrderRequest) -> OrderRequestResponse:
    response = OrderRequestResponse.model_validate(request)
    response.items = [item for item in response.items if item.removed_at is None]
    return response


async def _get_locked_for_write(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequest, OrderRequestAccessDenied | OrderRequestNotFound]:
    if not actor.permissions.intersection(
        {
            PermissionCode.ORDER_REQUESTS_UPDATE_SELF,
            PermissionCode.ORDER_REQUESTS_UPDATE_ANY,
        }
    ):
        return Err(OrderRequestAccessDenied())

    request = await request_dao.get_for_update(db, order_request_id)

    if request is Empty:
        return Err(OrderRequestNotFound(order_request_id))

    request = cast("OrderRequest", request)
    decision = can_access_order_request(
        actor,
        owner_user_id=request.created_by_user_id,
        write=True,
    )

    if decision is not AuthorizationDecision.ALLOW:
        return Err(OrderRequestNotFound(order_request_id))

    return Ok(request)


async def _get_locked_for_review(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequest, OrderRequestAccessDenied | OrderRequestNotFound]:
    if PermissionCode.ORDER_REQUESTS_REVIEW not in actor.permissions:
        return Err(OrderRequestAccessDenied())

    request = await request_dao.get_for_update(db, order_request_id)

    if request is Empty:
        return Err(OrderRequestNotFound(order_request_id))

    return Ok(request)


def _editable_error(request: OrderRequest) -> OrderRequestNotEditable | None:
    status = OrderRequestStatus(request.status)

    if can_edit_order_request(status):
        return None

    return OrderRequestNotEditable(status)


async def _commit_mutation(
    db: AsyncSession,
    *,
    request: OrderRequest,
    event: OrderRequestEventType,
    actor: Actor,
    changes: list[dict[str, object]],
    extra_history: tuple[OrderRequestEventType, list[dict[str, object]]] | None = None,
) -> None:
    try:
        await request_dao.flush(db)
        await history_dao.create(
            db,
            order_request_id=request.id,
            event=event,
            actor_user_id=actor.user_id,
            changes=changes,
        )
        if extra_history is not None:
            extra_event, extra_changes = extra_history
            await history_dao.create(
                db,
                order_request_id=request.id,
                event=extra_event,
                actor_user_id=actor.user_id,
                changes=extra_changes,
            )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise


async def create(
    db: AsyncSession,
    actor: Actor,
    request_in: OrderRequestCreate,
) -> Result[OrderRequestResponse, CreateOrderRequestError]:
    if PermissionCode.ORDER_REQUESTS_CREATE_SELF not in actor.permissions:
        return Err(OrderRequestAccessDenied())

    period = await period_dao.get_for_update(db, request_in.order_period_id)

    if period is Empty:
        return Err(OrderPeriodNotFound(request_in.order_period_id))

    period = cast("OrderPeriod", period)
    now = datetime_now()
    period_status = resolve_order_period_status(
        period.opens_at,
        period.closes_at,
        now,
    )

    if period_status is not OrderPeriodStatus.OPEN:
        return Err(OrderRequestPeriodNotOpen(request_in.order_period_id))

    listings: dict[int, CardListingSnapshot] = {}

    for item_in in request_in.items:
        listing = await listing_dao.get_snapshot(db, item_in.card_listing_id)

        if listing is Empty:
            return Err(OrderRequestCardListingNotFound(item_in.card_listing_id))

        listings[item_in.card_listing_id] = listing

    try:
        request = await request_dao.create(
            db,
            order_period_id=request_in.order_period_id,
            created_by_user_id=actor.user_id,
            note=request_in.note,
        )

        for item_in in request_in.items:
            item = await item_dao.create_from_listing(
                db,
                order_request_id=request.id,
                listing=listings[item_in.card_listing_id],
                requested_quantity=item_in.requested_quantity,
            )
            request.items.append(item)

        await history_dao.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.CREATED,
            actor_user_id=actor.user_id,
            occurred_at=now,
            changes=[],
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(_response(request))


async def get_one(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequestResponse, ReadOrderRequestError]:
    if not actor.permissions.intersection(
        {
            PermissionCode.ORDER_REQUESTS_READ_SELF,
            PermissionCode.ORDER_REQUESTS_READ_ANY,
        }
    ):
        return Err(OrderRequestAccessDenied())

    request = await request_dao.get(db, order_request_id)

    if request is Empty:
        return Err(OrderRequestNotFound(order_request_id))

    request = cast("OrderRequest", request)
    decision = can_access_order_request(
        actor,
        owner_user_id=request.created_by_user_id,
        write=False,
    )

    if decision is not AuthorizationDecision.ALLOW:
        return Err(OrderRequestNotFound(order_request_id))

    return Ok(_response(request))


async def get_multi(
    db: AsyncSession,
    actor: Actor,
    *,
    page: int = 1,
    shows: int = 100,
    order_period_id: int | None = None,
    status: OrderRequestStatus | None = None,
) -> Result[tuple[list[OrderRequestResponse], int], OrderRequestAccessDenied]:
    owner_user_id, access_error = _can_list(actor)

    if access_error is not None:
        return Err(access_error)

    requests, total = await request_dao.get_multi(
        db,
        page=(page - 1) * shows,
        shows=shows,
        owner_user_id=owner_user_id,
        order_period_id=order_period_id,
        status=status,
    )

    return Ok(([_response(request) for request in requests], total))


async def get_history(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    *,
    page: int = 1,
    shows: int = 100,
) -> Result[list[OrderRequestHistoryResponse], ReadOrderRequestError]:
    visible_request = await get_one(db, actor, order_request_id)

    match visible_request:
        case Err(error):
            return Err(error)
        case Ok():
            pass

    history = await history_dao.get_for_request(
        db,
        order_request_id=order_request_id,
        page=(page - 1) * shows,
        shows=shows,
    )

    return Ok([OrderRequestHistoryResponse.model_validate(entry) for entry in history])


async def update_note(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    request_in: OrderRequestUpdate,
) -> Result[OrderRequestResponse, MutateOrderRequestError]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    edit_error = _editable_error(request)

    if edit_error is not None:
        return Err(edit_error)

    if request.note == request_in.note:
        return Ok(_response(request))

    old_note = request.note
    request.note = request_in.note
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.UPDATED,
        actor=actor,
        changes=[_change("note", old_note, request.note)],
    )

    return Ok(_response(request))


async def add_item(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    item_in: OrderRequestItemCreate,
) -> Result[OrderRequestResponse, AddOrderRequestItemError]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    status = OrderRequestStatus(request.status)

    if not can_add_order_request_item(status):
        return Err(OrderRequestItemCannotBeAdded(status))

    if any(item.card_listing_id == item_in.card_listing_id for item in request.items):
        return Err(OrderRequestItemAlreadyExists(request.id, item_in.card_listing_id))

    listing = await listing_dao.get_snapshot(db, item_in.card_listing_id)

    if listing is Empty:
        return Err(OrderRequestCardListingNotFound(item_in.card_listing_id))

    try:
        item = await item_dao.create_from_listing(
            db,
            order_request_id=request.id,
            listing=listing,
            requested_quantity=item_in.requested_quantity,
        )
        request.items.append(item)
        await history_dao.create(
            db,
            order_request_id=request.id,
            event=OrderRequestEventType.ITEM_ADDED,
            actor_user_id=actor.user_id,
            changes=[
                _change("cardListingId", None, item.card_listing_id),
                _change("requestedQuantity", None, item.requested_quantity),
                _change("agreedQuantity", None, item.agreed_quantity),
            ],
        )
        await db.commit()
    except DAOError:
        await db.rollback()
        raise

    return Ok(_response(request))


async def update_item(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    item_id: int,
    item_in: OrderRequestItemUpdate,
) -> Result[OrderRequestResponse, MutateOrderRequestItemError]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    edit_error = _editable_error(request)

    if edit_error is not None:
        return Err(edit_error)

    item = next((item for item in request.items if item.id == item_id), None)

    if item is None or item.removed_at is not None:
        return Err(OrderRequestItemNotFound(request.id, item_id))

    changes: list[dict[str, object]] = []
    updates = item_in.model_dump(exclude_unset=True)
    requested_quantity = updates.get(
        "requested_quantity",
        item.requested_quantity,
    )
    agreed_quantity = updates.get("agreed_quantity", item.agreed_quantity)

    if agreed_quantity > requested_quantity:
        return Err(
            OrderRequestInvalidQuantities(
                requested_quantity=requested_quantity,
                agreed_quantity=agreed_quantity,
            )
        )

    for field, public_field in (
        ("requested_quantity", "requestedQuantity"),
        ("agreed_quantity", "agreedQuantity"),
    ):
        if field not in updates:
            continue

        old_value = getattr(item, field)
        new_value = updates[field]

        if old_value != new_value:
            setattr(item, field, new_value)
            changes.append(_change(public_field, old_value, new_value))

    if not changes:
        return Ok(_response(request))

    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.ITEM_UPDATED,
        actor=actor,
        changes=changes,
    )

    return Ok(_response(request))


async def remove_item(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    item_id: int,
) -> Result[OrderRequestResponse, MutateOrderRequestItemError]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    edit_error = _editable_error(request)

    if edit_error is not None:
        return Err(edit_error)

    item = next((item for item in request.items if item.id == item_id), None)

    if item is None:
        return Err(OrderRequestItemNotFound(request.id, item_id))

    if item.removed_at is not None:
        return Ok(_response(request))

    now = datetime_now()
    item.removed_at = now
    item.removed_by_user_id = actor.user_id
    active_items = [
        candidate for candidate in request.items if candidate.removed_at is None
    ]
    extra_history = None

    if not active_items:
        old_status = OrderRequestStatus(request.status)
        request.status = OrderRequestStatus.CANCELLED
        request.cancelled_at = now
        request.cancelled_by_user_id = actor.user_id
        extra_history = (
            OrderRequestEventType.STATUS_CHANGED,
            [_change("status", old_status.value, OrderRequestStatus.CANCELLED.value)],
        )

    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.ITEM_REMOVED,
        actor=actor,
        changes=[
            _change("removedAt", None, now.isoformat()),
            _change("removedByUserId", None, actor.user_id),
        ],
        extra_history=extra_history,
    )

    return Ok(_response(request))


async def restore_item(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    item_id: int,
) -> Result[OrderRequestResponse, MutateOrderRequestItemError]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    item = next((item for item in request.items if item.id == item_id), None)

    if item is None:
        return Err(OrderRequestItemNotFound(request.id, item_id))

    status = OrderRequestStatus(request.status)
    prices = (item.card_unit_price, item.tax_unit_price)

    if not can_restore_order_request_item(status, prices):
        return Err(OrderRequestItemCannotBeRestored(status))

    if item.removed_at is None:
        return Ok(_response(request))

    old_removed_at = item.removed_at
    old_removed_by = item.removed_by_user_id
    item.removed_at = None
    item.removed_by_user_id = None
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.ITEM_RESTORED,
        actor=actor,
        changes=[
            _change("removedAt", old_removed_at.isoformat(), None),
            _change("removedByUserId", old_removed_by, None),
        ],
    )

    return Ok(_response(request))


async def _change_review_status(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    *,
    target: OrderRequestStatus,
    allowed_sources: frozenset[OrderRequestStatus],
) -> Result[OrderRequestResponse, ReviewOrderRequestError]:
    locked = await _get_locked_for_review(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    current = OrderRequestStatus(request.status)

    if current not in allowed_sources or not can_transition_order_request(
        current, target
    ):
        return Err(OrderRequestInvalidTransition(current, target))

    changes = [_change("status", current.value, target.value)]

    if target is OrderRequestStatus.IN_REVIEW and request.shipping_price is None:
        request.shipping_price = DEFAULT_SHIPPING_PRICE
        changes.append(_change("shippingPrice", None, DEFAULT_SHIPPING_PRICE))

    if target is OrderRequestStatus.IN_REVIEW and request.cancelled_at is not None:
        changes.extend(
            [
                _change("cancelledAt", request.cancelled_at.isoformat(), None),
                _change("cancelledByUserId", request.cancelled_by_user_id, None),
            ]
        )
        request.cancelled_at = None
        request.cancelled_by_user_id = None

    request.status = target
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.STATUS_CHANGED,
        actor=actor,
        changes=changes,
    )

    return Ok(_response(request))


async def start_review(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequestResponse, ReviewOrderRequestError]:
    result = await _change_review_status(
        db,
        actor,
        order_request_id,
        target=OrderRequestStatus.IN_REVIEW,
        allowed_sources=frozenset({OrderRequestStatus.SUBMITTED}),
    )

    return result


async def accept(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequestResponse, ReviewOrderRequestError]:
    locked = await _get_locked_for_review(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    current = OrderRequestStatus(request.status)

    if not can_transition_order_request(current, OrderRequestStatus.ACCEPTED):
        return Err(OrderRequestInvalidTransition(current, OrderRequestStatus.ACCEPTED))

    active_items = [item for item in request.items if item.removed_at is None]
    prices = [
        (item.card_unit_price, item.tax_unit_price)
        for item in active_items
    ]

    if not active_items:
        return Err(OrderRequestCannotAccept("no_active_items"))

    if not can_accept_order_request(prices):
        return Err(OrderRequestCannotAccept("incomplete_pricing"))

    if request.shipping_price is None:
        return Err(OrderRequestCannotAccept("missing_shipping_price"))

    request.status = OrderRequestStatus.ACCEPTED
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.STATUS_CHANGED,
        actor=actor,
        changes=[
            _change(
                "status",
                current.value,
                OrderRequestStatus.ACCEPTED.value,
            )
        ],
    )

    return Ok(_response(request))


async def reject(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequestResponse, ReviewOrderRequestError]:
    return await _change_review_status(
        db,
        actor,
        order_request_id,
        target=OrderRequestStatus.REJECTED,
        allowed_sources=frozenset(
            {OrderRequestStatus.SUBMITTED, OrderRequestStatus.IN_REVIEW}
        ),
    )


async def reopen_for_review(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[OrderRequestResponse, ReviewOrderRequestError]:
    return await _change_review_status(
        db,
        actor,
        order_request_id,
        target=OrderRequestStatus.IN_REVIEW,
        allowed_sources=frozenset(
            {
                OrderRequestStatus.ACCEPTED,
                OrderRequestStatus.REJECTED,
                OrderRequestStatus.CANCELLED,
            }
        ),
    )


async def cancel(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
) -> Result[
    OrderRequestResponse,
    OrderRequestAccessDenied | OrderRequestNotFound | OrderRequestInvalidTransition,
]:
    locked = await _get_locked_for_write(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    current = OrderRequestStatus(request.status)
    is_owner = actor.user_id == request.created_by_user_id
    owner_sources = {
        OrderRequestStatus.SUBMITTED,
        OrderRequestStatus.IN_REVIEW,
        OrderRequestStatus.ACCEPTED,
    }
    admin_sources = {OrderRequestStatus.SUBMITTED, OrderRequestStatus.IN_REVIEW}
    allowed_sources = owner_sources if is_owner else admin_sources

    if current not in allowed_sources:
        return Err(OrderRequestInvalidTransition(current, OrderRequestStatus.CANCELLED))

    now = datetime_now()
    request.status = OrderRequestStatus.CANCELLED
    request.cancelled_at = now
    request.cancelled_by_user_id = actor.user_id
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.STATUS_CHANGED,
        actor=actor,
        changes=[
            _change("status", current.value, OrderRequestStatus.CANCELLED.value),
            _change("cancelledAt", None, now.isoformat()),
            _change("cancelledByUserId", None, actor.user_id),
        ],
    )

    return Ok(_response(request))


async def update_pricing(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    item_id: int,
    pricing_in: OrderRequestItemPricingUpdate,
) -> Result[OrderRequestResponse, PriceOrderRequestItemError]:
    locked = await _get_locked_for_review(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    status = OrderRequestStatus(request.status)

    if status not in {OrderRequestStatus.IN_REVIEW, OrderRequestStatus.ACCEPTED}:
        return Err(OrderRequestNotEditable(status))

    item = next((item for item in request.items if item.id == item_id), None)

    if item is None:
        return Err(OrderRequestItemNotFound(request.id, item_id))

    changes: list[dict[str, object]] = []

    for field, public_field in (
        ("card_unit_price", "cardUnitPrice"),
        ("tax_unit_price", "taxUnitPrice"),
    ):
        old_value = getattr(item, field)
        new_value = getattr(pricing_in, field)

        if old_value != new_value:
            setattr(item, field, new_value)
            changes.append(_change(public_field, old_value, new_value))

    if not changes:
        return Ok(_response(request))

    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.ITEM_UPDATED,
        actor=actor,
        changes=changes,
    )

    return Ok(_response(request))


async def update_order_pricing(
    db: AsyncSession,
    actor: Actor,
    order_request_id: int,
    pricing_in: OrderRequestPricingUpdate,
) -> Result[OrderRequestResponse, PriceOrderRequestError]:
    locked = await _get_locked_for_review(db, actor, order_request_id)

    match locked:
        case Err(error):
            return Err(error)
        case Ok(request):
            pass

    status = OrderRequestStatus(request.status)

    if status is not OrderRequestStatus.IN_REVIEW:
        return Err(OrderRequestNotEditable(status))

    old_value = request.shipping_price
    new_value = pricing_in.shipping_price

    if old_value == new_value:
        return Ok(_response(request))

    request.shipping_price = new_value
    await _commit_mutation(
        db,
        request=request,
        event=OrderRequestEventType.UPDATED,
        actor=actor,
        changes=[_change("shippingPrice", old_value, new_value)],
    )

    return Ok(_response(request))
