from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.api.order_requests.domain import (
    OrderRequestCreate,
    OrderRequestItemCreate,
    OrderRequestItemPricingUpdate,
    OrderRequestItemUpdate,
    OrderRequestStatus,
)


def test_create_requires_at_least_one_item() -> None:
    with pytest.raises(ValidationError):
        OrderRequestCreate(order_period_id=1, items=[])


def test_create_rejects_duplicate_card_listings() -> None:
    with pytest.raises(ValidationError):
        OrderRequestCreate(
            order_period_id=1,
            items=[
                OrderRequestItemCreate(card_listing_id=7, requested_quantity=1),
                OrderRequestItemCreate(card_listing_id=7, requested_quantity=2),
            ],
        )


def test_item_create_requires_positive_identifiers_and_quantity() -> None:
    for payload in (
        {"cardListingId": 0, "requestedQuantity": 1},
        {"cardListingId": 1, "requestedQuantity": 0},
    ):
        with pytest.raises(ValidationError):
            OrderRequestItemCreate.model_validate(payload)


def test_item_update_distinguishes_omitted_quantities() -> None:
    update = OrderRequestItemUpdate.model_validate({"agreedQuantity": 0})

    assert update.model_fields_set == {"agreed_quantity"}
    assert update.requested_quantity is None
    assert update.agreed_quantity == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"requestedQuantity": None},
        {"agreedQuantity": None},
        {"requestedQuantity": 0},
        {"agreedQuantity": -1},
    ],
)
def test_item_update_rejects_empty_null_or_invalid_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        OrderRequestItemUpdate.model_validate(payload)


def test_pricing_rounds_half_up_to_two_decimals() -> None:
    pricing = OrderRequestItemPricingUpdate(
        card_unit_price=Decimal("1.005"),
        shipping_unit_price=Decimal("0.004"),
        tax_unit_price=Decimal("0"),
    )

    assert pricing.card_unit_price == Decimal("1.01")
    assert pricing.shipping_unit_price == Decimal("0.00")
    assert pricing.tax_unit_price == Decimal("0.00")
    assert pricing.final_unit_price == Decimal("1.01")


def test_pricing_applies_default_shipping_and_tax() -> None:
    pricing = OrderRequestItemPricingUpdate(card_unit_price=Decimal("10.00"))

    assert pricing.shipping_unit_price == Decimal("5.00")
    assert pricing.tax_unit_price == Decimal("1.60")
    assert pricing.final_unit_price == Decimal("16.60")


def test_pricing_rejects_negative_components() -> None:
    with pytest.raises(ValidationError):
        OrderRequestItemPricingUpdate(
            card_unit_price=Decimal("-0.01"),
            shipping_unit_price=Decimal("0"),
            tax_unit_price=Decimal("0"),
        )


def test_quantity_and_pricing_contracts_reject_fields_owned_by_the_other() -> None:
    with pytest.raises(ValidationError):
        OrderRequestItemUpdate.model_validate(
            {"agreedQuantity": 1, "cardUnitPrice": "2.00"}
        )

    with pytest.raises(ValidationError):
        OrderRequestItemPricingUpdate.model_validate(
            {
                "cardUnitPrice": "1.00",
                "shippingUnitPrice": "0.00",
                "taxUnitPrice": "0.00",
                "finalUnitPrice": "1.00",
            }
        )


def test_status_contract_contains_only_v1_states() -> None:
    assert {status.value for status in OrderRequestStatus} == {
        "submitted",
        "in_review",
        "accepted",
        "rejected",
        "cancelled",
    }
