import json
from collections import Counter

from src.application import app
from src.core.schema import (
    ErrorResponse,
    PaginatedResponse,
    ValidationErrorResponse,
)


def test_openapi_generates_a_json_serializable_document() -> None:
    schema = app.openapi()
    serialized = json.dumps(schema)

    assert json.loads(serialized)["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Free Win"
    assert schema["paths"]
    assert schema["components"]["schemas"]


def test_openapi_operation_ids_are_unique() -> None:
    operation_ids = [
        operation["operationId"]
        for path_item in app.openapi()["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    duplicates = [
        operation_id
        for operation_id, occurrences in Counter(operation_ids).items()
        if occurrences > 1
    ]

    assert duplicates == []


def test_openapi_exposes_project_metadata_and_ordered_tags() -> None:
    schema = app.openapi()

    assert schema["info"]["version"] == "0.1.0"
    assert schema["info"]["license"] == {"name": "MIT"}
    assert "Autenticación temporal" in schema["info"]["description"]
    assert [tag["name"] for tag in schema["tags"]] == [
        "order-periods",
        "order-requests",
        "cards",
        "card-listings",
        "users",
        "user-addresses",
        "roles",
        "permissions",
        "user-roles",
    ]
    assert "securitySchemes" not in schema.get("components", {})


def test_shared_http_models_describe_errors_validation_and_pagination() -> None:
    components = app.openapi()["components"]["schemas"]
    error_schema = components[ErrorResponse.__name__]
    validation_schema = components[ValidationErrorResponse.__name__]
    pagination_schema = PaginatedResponse[ErrorResponse].model_json_schema()

    assert error_schema["required"] == ["detail"]
    assert validation_schema["properties"]["detail"]["type"] == "array"
    assert pagination_schema["required"] == ["items", "total"]
    assert pagination_schema["properties"]["total"]["minimum"] == 0
    assert {
        "UserListResponse",
        "UserAddressListResponse",
        "UserRoleListResponse",
        "CardListResponse",
        "CardListingListResponse",
        "OrderPeriodListResponse",
        "OrderRequestListResponse",
    } <= components.keys()


def test_order_request_catalog_keeps_forbidden_and_conflict_distinct() -> None:
    schema = app.openapi()
    responses = schema["paths"]["/order-requests/{order_request_id}/start-review"][
        "post"
    ]["responses"]

    assert responses["403"]["description"] == (
        "La identidad no posee el permiso requerido."
    )
    assert responses["409"]["description"] == (
        "La transición o sus precondiciones no son válidas."
    )
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ValidationErrorResponse"
    )
