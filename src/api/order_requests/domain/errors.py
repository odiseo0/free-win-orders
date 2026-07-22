from dataclasses import dataclass

from .entities import OrderRequestStatus


@dataclass(frozen=True, slots=True)
class OrderRequestAccessDenied:
    pass


@dataclass(frozen=True, slots=True)
class OrderRequestNotFound:
    order_request_id: int


@dataclass(frozen=True, slots=True)
class OrderRequestItemNotFound:
    order_request_id: int
    item_id: int


@dataclass(frozen=True, slots=True)
class OrderRequestItemAlreadyExists:
    order_request_id: int
    card_listing_id: int


@dataclass(frozen=True, slots=True)
class OrderRequestPeriodNotOpen:
    order_period_id: int


@dataclass(frozen=True, slots=True)
class OrderRequestCardListingNotFound:
    card_listing_id: int


@dataclass(frozen=True, slots=True)
class OrderRequestInvalidTransition:
    current: OrderRequestStatus
    target: OrderRequestStatus


@dataclass(frozen=True, slots=True)
class OrderRequestNotEditable:
    status: OrderRequestStatus


@dataclass(frozen=True, slots=True)
class OrderRequestCannotAccept:
    reason: str


@dataclass(frozen=True, slots=True)
class OrderRequestItemCannotBeAdded:
    status: OrderRequestStatus


@dataclass(frozen=True, slots=True)
class OrderRequestItemCannotBeRestored:
    status: OrderRequestStatus
