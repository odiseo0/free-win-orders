from decimal import Decimal

from src.api.roles.domain import Actor, AuthorizationDecision, PermissionCode

from .entities import OrderRequestStatus

type PriceComponents = tuple[Decimal | None, Decimal | None, Decimal | None]


_ALLOWED_TRANSITIONS = frozenset(
    {
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.REJECTED),
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.CANCELLED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.ACCEPTED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.REJECTED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.CANCELLED),
        (OrderRequestStatus.ACCEPTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.REJECTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.CANCELLED, OrderRequestStatus.IN_REVIEW),
    }
)


def can_transition_order_request(
    current: OrderRequestStatus, target: OrderRequestStatus
) -> bool:
    return (current, target) in _ALLOWED_TRANSITIONS


def can_edit_order_request(status: OrderRequestStatus) -> bool:
    return status in {
        OrderRequestStatus.SUBMITTED,
        OrderRequestStatus.IN_REVIEW,
        OrderRequestStatus.ACCEPTED,
    }


def can_add_order_request_item(status: OrderRequestStatus) -> bool:
    return status in {
        OrderRequestStatus.SUBMITTED,
        OrderRequestStatus.IN_REVIEW,
    }


def _has_complete_pricing(prices: PriceComponents) -> bool:
    return all(price is not None for price in prices)


def can_restore_order_request_item(
    status: OrderRequestStatus, prices: PriceComponents
) -> bool:
    if not can_edit_order_request(status):
        return False

    return status is not OrderRequestStatus.ACCEPTED or _has_complete_pricing(prices)


def can_accept_order_request(active_item_prices: list[PriceComponents]) -> bool:
    return bool(active_item_prices) and all(
        _has_complete_pricing(prices) for prices in active_item_prices
    )


def can_access_order_request(
    actor: Actor, *, owner_user_id: int, write: bool
) -> AuthorizationDecision:
    own_permission = (
        PermissionCode.ORDER_REQUESTS_UPDATE_SELF
        if write
        else PermissionCode.ORDER_REQUESTS_READ_SELF
    )
    any_permission = (
        PermissionCode.ORDER_REQUESTS_UPDATE_ANY
        if write
        else PermissionCode.ORDER_REQUESTS_READ_ANY
    )

    if any_permission in actor.permissions:
        return AuthorizationDecision.ALLOW

    if actor.user_id == owner_user_id and own_permission in actor.permissions:
        return AuthorizationDecision.ALLOW

    return AuthorizationDecision.HIDDEN
