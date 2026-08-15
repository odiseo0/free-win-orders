from decimal import Decimal

import pytest

from src.api.order_requests.domain import (
    OrderRequestStatus,
    can_accept_order_request,
    can_add_order_request_item,
    can_edit_order_request,
    can_restore_order_request_item,
    can_transition_order_request,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.REJECTED),
        (OrderRequestStatus.SUBMITTED, OrderRequestStatus.CANCELLED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.ACCEPTED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.REJECTED),
        (OrderRequestStatus.IN_REVIEW, OrderRequestStatus.CANCELLED),
        (OrderRequestStatus.ACCEPTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.REJECTED, OrderRequestStatus.IN_REVIEW),
        (OrderRequestStatus.CANCELLED, OrderRequestStatus.IN_REVIEW),
    ],
)
def test_confirmed_admin_transitions_are_allowed(
    current: OrderRequestStatus, target: OrderRequestStatus
) -> None:
    assert can_transition_order_request(current, target)


@pytest.mark.parametrize("current", list(OrderRequestStatus))
@pytest.mark.parametrize("target", list(OrderRequestStatus))
def test_transition_matrix_rejects_every_unconfirmed_pair(
    current: OrderRequestStatus, target: OrderRequestStatus
) -> None:
    allowed = {
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

    expected = (current, target) in allowed
    assert can_transition_order_request(current, target) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OrderRequestStatus.SUBMITTED, True),
        (OrderRequestStatus.IN_REVIEW, True),
        (OrderRequestStatus.ACCEPTED, True),
        (OrderRequestStatus.REJECTED, False),
        (OrderRequestStatus.CANCELLED, False),
    ],
)
def test_content_editing_depends_on_status(
    status: OrderRequestStatus, expected: bool
) -> None:
    assert can_edit_order_request(status) is expected


def test_accepted_request_rejects_new_items() -> None:
    assert not can_add_order_request_item(OrderRequestStatus.ACCEPTED)
    assert can_add_order_request_item(OrderRequestStatus.IN_REVIEW)


def test_accepted_request_restores_only_fully_priced_items() -> None:
    complete = (Decimal("1.00"), Decimal("0.20"))
    incomplete = (Decimal("1.00"), None)

    assert can_restore_order_request_item(OrderRequestStatus.ACCEPTED, complete)
    assert not can_restore_order_request_item(OrderRequestStatus.ACCEPTED, incomplete)


def test_acceptance_requires_active_fully_priced_items() -> None:
    assert can_accept_order_request(
        [(Decimal("1.00"), Decimal("0.20"))]
    )
    assert not can_accept_order_request([])
    assert not can_accept_order_request([(Decimal("1.00"), None)])
