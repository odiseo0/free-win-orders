from src.application import app


PAGINATED_PATHS = (
    "/users/",
    "/user-addresses/",
    "/user-roles/",
)


def test_paginated_lists_use_items_total_and_one_based_limits() -> None:
    schema = app.openapi()

    for path in PAGINATED_PATHS:
        operation = schema["paths"][path]["get"]
        response_schema = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        component_name = response_schema["$ref"].rsplit("/", 1)[-1]
        component = schema["components"]["schemas"][component_name]
        parameters = {
            parameter["name"]: parameter for parameter in operation["parameters"]
        }

        assert set(component["properties"]) == {"items", "total"}
        assert parameters["page"]["schema"]["minimum"] == 1
        assert parameters["page"]["schema"]["default"] == 1
        assert parameters["shows"]["schema"]["minimum"] == 1
        assert parameters["shows"]["schema"]["maximum"] == 100


def test_non_paginated_catalogs_remain_arrays() -> None:
    paths = app.openapi()["paths"]

    for path in ("/roles/", "/permissions/"):
        response_schema = paths[path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert response_schema["type"] == "array"


def test_all_path_identifiers_are_positive() -> None:
    for path_item in app.openapi()["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue

            for parameter in operation.get("parameters", []):
                if parameter["in"] == "path":
                    assert parameter["schema"]["exclusiveMinimum"] == 0


def test_successful_deletes_return_204_without_content() -> None:
    paths = app.openapi()["paths"]
    delete_paths = (
        "/users/{user_id}",
        "/user-addresses/{user_address_id}",
        "/user-roles/{user_role_id}",
        "/roles/{role_id}",
    )

    for path in delete_paths:
        responses = paths[path]["delete"]["responses"]

        assert "204" in responses
        assert "content" not in responses["204"]


def test_resource_creations_return_201() -> None:
    paths = app.openapi()["paths"]
    create_paths = (
        "/users/",
        "/user-addresses/",
        "/user-roles/",
        "/roles/",
        "/order-periods/",
        "/order-requests/",
        "/order-requests/{order_request_id}/items",
    )

    for path in create_paths:
        assert "201" in paths[path]["post"]["responses"]


def test_main_aliases_and_examples_are_published() -> None:
    schemas = app.openapi()["components"]["schemas"]
    order_create = schemas["OrderRequestCreate"]
    order_response = schemas["OrderRequestResponse"]
    pricing_update = schemas["OrderRequestItemPricingUpdate"]
    user_create = schemas["UserCreate"]
    user_response = schemas["UserResponse"]

    assert "orderPeriodId" in order_create["properties"]
    assert order_create["properties"]["orderPeriodId"]["examples"] == [12]
    assert "cardListingId" in schemas["OrderRequestItemCreate"]["properties"]
    assert order_response["properties"]["agreedTotal"]["readOnly"] is True
    assert order_response["examples"]
    assert pricing_update["properties"]["cardUnitPrice"]["examples"] == ["3.50"]
    assert user_create["properties"]["password"]["writeOnly"] is True
    assert "password" not in user_response["properties"]
