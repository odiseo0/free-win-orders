from collections.abc import Iterator

from src.application import app


def _operations_for_tag(tag: str) -> Iterator[dict[str, object]]:
    for path_item in app.openapi()["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and tag in operation.get("tags", []):
                yield operation


def test_order_components_expose_stable_unique_operation_ids() -> None:
    order_period_ids = {
        operation["operationId"]
        for operation in _operations_for_tag("order-periods")
    }
    order_request_ids = {
        operation["operationId"]
        for operation in _operations_for_tag("order-requests")
    }

    assert order_period_ids == {
        "createOrderPeriod",
        "listOrderPeriods",
        "getOrderPeriodHistory",
        "getOrderPeriod",
        "updateOrderPeriod",
        "closeOrderPeriod",
    }
    assert order_request_ids == {
        "createOrderRequest",
        "listOrderRequests",
        "getOrderRequestHistory",
        "getOrderRequest",
        "updateOrderRequestNote",
        "addOrderRequestItem",
        "updateOrderRequestItem",
        "removeOrderRequestItem",
        "restoreOrderRequestItem",
        "startOrderRequestReview",
        "acceptOrderRequest",
        "rejectOrderRequest",
        "cancelOrderRequest",
        "reopenOrderRequestForReview",
        "updateOrderRequestPricing",
        "updateOrderRequestItemPricing",
    }
    assert order_period_ids.isdisjoint(order_request_ids)


def test_order_components_document_every_operation_in_spanish() -> None:
    operations = [
        *_operations_for_tag("order-periods"),
        *_operations_for_tag("order-requests"),
    ]

    assert all(operation.get("summary") for operation in operations)
    assert all(operation.get("description") for operation in operations)


def test_order_request_schema_documents_money_snapshots_and_nullability() -> None:
    schemas = app.openapi()["components"]["schemas"]
    item = schemas["OrderRequestItemResponse"]["properties"]
    order = schemas["OrderRequestResponse"]

    assert "snapshot" in item["cardName"]["description"]
    assert "USD" in item["estimatedUnitPrice"]["description"]
    assert "nulo" in item["finalUnitPrice"]["description"]
    assert "shippingUnitPrice" not in item
    assert "ISO 4217" in order["properties"]["currency"]["description"]
    assert "una sola vez" in order["properties"]["shippingPrice"]["description"]
    assert order["examples"][0]["status"] == "submitted"
    assert {"type": "null"} in order["properties"]["agreedTotal"]["anyOf"]


def test_order_period_schema_documents_dates_and_calculated_status() -> None:
    schemas = app.openapi()["components"]["schemas"]
    create = schemas["OrderPeriodCreate"]["properties"]
    response = schemas["OrderPeriodResponse"]

    assert "zona horaria" in create["opensAt"]["description"]
    assert "calculado" in response["properties"]["status"]["description"]
    assert response["examples"][0]["status"] == "open"


def test_order_period_operations_publish_only_their_real_error_statuses() -> None:
    paths = app.openapi()["paths"]

    assert set(paths["/order-periods/"]["post"]["responses"]) == {
        "201",
        "401",
        "403",
        "409",
        "422",
    }
    assert set(paths["/order-periods/"]["get"]["responses"]) == {
        "200",
        "401",
        "403",
        "422",
    }
    assert set(paths["/order-periods/{order_period_id}"]["get"]["responses"]) == {
        "200",
        "401",
        "403",
        "404",
        "422",
    }


def test_hidden_order_periods_are_documented_without_revealing_them() -> None:
    operation = app.openapi()["paths"]["/order-periods/{order_period_id}"]["get"]

    assert "se presenta como inexistente" in operation["description"]
    assert "no es visible" in operation["responses"]["404"]["description"]


def test_order_request_conflicts_include_representative_examples() -> None:
    paths = app.openapi()["paths"]
    create_responses = paths["/order-requests/"]["post"]["responses"]
    accept_responses = paths[
        "/order-requests/{order_request_id}/accept"
    ]["post"]["responses"]

    assert create_responses["409"]["content"]["application/json"]["example"] == {
        "detail": "El Pedido no está abierto para recibir Órdenes"
    }
    examples = accept_responses["409"]["content"]["application/json"]["examples"]
    assert {
        "invalidTransition",
        "incompletePrices",
        "missingShippingPrice",
    } <= examples.keys()
