from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.api.deliveries.domain import (
    DeliveryEventCreate,
    DeliveryMethod,
    DeliveryPreferenceUpdate,
    FulfillmentCreate,
    InternationalShipmentCreate,
)
from src.api.deliveries.repository import (
    DeliveryEvent,
    DeliveryFulfillment,
    DeliveryPreference,
    DeliveryShipment,
    DeliveryShipmentAllocation,
    DeliveryStage,
)
from src.api.order_requests.domain import OrderRequestStatus, can_transition_order_request
from src.api.roles.domain import USER_PERMISSIONS, PermissionCode
from src.application import app


def test_delivery_preference_requires_the_expected_address() -> None:
    shipping = DeliveryPreferenceUpdate(
        method=DeliveryMethod.NATIONAL_SHIPPING, user_address_id=7
    )
    pickup = DeliveryPreferenceUpdate(method=DeliveryMethod.PICKUP)

    assert shipping.user_address_id == 7
    assert pickup.user_address_id is None

    with pytest.raises(ValidationError):
        DeliveryPreferenceUpdate(method=DeliveryMethod.NATIONAL_SHIPPING)

    with pytest.raises(ValidationError):
        DeliveryPreferenceUpdate(method=DeliveryMethod.PICKUP, user_address_id=7)


def test_corrections_require_both_event_and_reason() -> None:
    with pytest.raises(ValidationError):
        DeliveryEventCreate(stage_key="organized", correction_of_event_id=1)

    correction = DeliveryEventCreate(
        stage_key="at_us_courier",
        correction_of_event_id=1,
        correction_reason="La etapa anterior se registró por error.",
        occurred_at=datetime.now(UTC),
    )

    assert correction.correction_reason is not None


def test_full_order_allocation_uses_null_items_and_rejects_duplicates() -> None:
    contract = InternationalShipmentCreate.model_validate(
        {
            "orderPeriodId": 4,
            "name": "Compra 1",
            "allocations": [{"orderRequestId": 8, "items": None}],
        }
    )
    assert contract.allocations[0].items is None

    with pytest.raises(ValidationError):
        InternationalShipmentCreate.model_validate(
            {
                "orderPeriodId": 4,
                "name": "Compra 1",
                "allocations": [
                    {"orderRequestId": 8},
                    {"orderRequestId": 8},
                ],
            }
        )


def test_national_cost_requires_its_payer() -> None:
    with pytest.raises(ValidationError):
        FulfillmentCreate(shipping_cost="5.00")

    contract = FulfillmentCreate(shipping_cost="5.00", cost_payer="recipient")
    assert str(contract.shipping_cost) == "5.00"


def test_delivery_models_use_owned_tables_and_foreign_keys() -> None:
    assert DeliveryStage.__tablename__ == "delivery_stages"
    assert DeliveryShipment.__tablename__ == "delivery_shipments"
    assert DeliveryShipmentAllocation.__tablename__ == "delivery_shipment_allocations"
    assert DeliveryEvent.__tablename__ == "delivery_events"
    assert DeliveryPreference.__tablename__ == "delivery_preferences"
    assert DeliveryFulfillment.__tablename__ == "delivery_fulfillments"

    allocation_fk = next(
        iter(DeliveryShipmentAllocation.__table__.c.order_request_item_id.foreign_keys)
    )
    assert allocation_fk.target_fullname == "order_request_items.id"


def test_delivery_models_have_safe_construction_defaults() -> None:
    stage = DeliveryStage(
        scope="international",
        key="purchase_confirmed",
        name="Compra confirmada",
        position=0,
    )
    shipment = DeliveryShipment(
        kind="international",
        order_period_id=4,
        name="Compra 1",
        current_stage_id=1,
    )
    preference = DeliveryPreference(
        order_request_id=8,
        method="pickup",
    )
    fulfillment = DeliveryFulfillment(
        order_request_id=8,
        method="pickup",
        current_stage_id=1,
    )
    event = DeliveryEvent(
        shipment_id=1,
        source="admin",
        actor_user_id=3,
        occurred_at=datetime.now(UTC),
    )

    assert stage.is_active
    assert shipment.external_references == []
    assert shipment.failure_count == 0
    assert preference.user_address_id is None
    assert fulfillment.shipping_cost is None
    assert event.recorded_at.tzinfo is not None


def test_paid_transition_and_user_delivery_permissions_are_public_rules() -> None:
    assert can_transition_order_request(
        OrderRequestStatus.ACCEPTED, OrderRequestStatus.PAID
    )
    assert can_transition_order_request(
        OrderRequestStatus.PAID, OrderRequestStatus.ACCEPTED
    )
    assert PermissionCode.DELIVERIES_READ_SELF in USER_PERMISSIONS
    assert PermissionCode.DELIVERIES_SELECT_SELF in USER_PERMISSIONS
    assert PermissionCode.DELIVERIES_REFRESH_SELF in USER_PERMISSIONS
    assert PermissionCode.DELIVERIES_MANAGE not in USER_PERMISSIONS


def test_delivery_routes_have_unique_operation_ids() -> None:
    schema = app.openapi()
    expected = {
        "/order-requests/{order_request_id}/mark-paid": "markOrderRequestPaid",
        "/order-requests/{order_request_id}/tracking": "getOrderRequestTracking",
        "/deliveries/international-shipments": "listInternationalShipments",
        "/delivery-stages": "listDeliveryStages",
    }
    for path, operation_id in expected.items():
        operation = "post" if path.endswith("mark-paid") else "get"
        assert schema["paths"][path][operation]["operationId"] == operation_id

    operations = []
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and set(operation.get("tags", [])).intersection(
                {"deliveries", "delivery-stages"}
            ):
                operations.append(operation)
    assert operations
    assert all(operation.get("summary") for operation in operations)
    assert all(operation.get("description") for operation in operations)
