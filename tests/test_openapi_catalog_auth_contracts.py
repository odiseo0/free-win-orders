from collections.abc import Iterator

from src.application import app


def _operations_for_tag(tag: str) -> Iterator[dict[str, object]]:
    for path_item in app.openapi()["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and tag in operation.get("tags", []):
                yield operation


def test_users_and_authorization_have_stable_operation_ids() -> None:
    expected = {
        "users": {
            "listUsers",
            "getUser",
            "createUser",
            "updateUser",
            "deleteUser",
            "setUserRole",
        },
        "user-addresses": {
            "listUserAddresses",
            "getUserAddress",
            "createUserAddress",
            "updateUserAddress",
            "deleteUserAddress",
        },
        "roles": {
            "listRoles",
            "getRole",
            "createRole",
            "updateRole",
            "deleteRole",
            "replaceRolePermissions",
        },
        "permissions": {"listPermissions"},
    }

    actual = {
        tag: {operation["operationId"] for operation in _operations_for_tag(tag)}
        for tag in expected
    }

    assert actual == expected
    assert len(set().union(*actual.values())) == sum(map(len, actual.values()))


def test_stage_four_operations_have_spanish_documentation() -> None:
    tags = (
        "users",
        "user-addresses",
        "roles",
        "permissions",
    )
    operations = [
        operation
        for tag in tags
        for operation in _operations_for_tag(tag)
    ]

    assert all(operation.get("summary") for operation in operations)
    assert all(operation.get("description") for operation in operations)


def test_password_is_write_only_and_absent_from_user_responses() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["UserCreate"]["properties"]["password"]["writeOnly"] is True
    assert schemas["UserUpdate"]["properties"]["password"]["writeOnly"] is True
    assert "password" not in schemas["UserResponse"]["properties"]


def test_user_and_address_permissions_are_explained() -> None:
    paths = app.openapi()["paths"]

    assert "permiso personal" in paths["/users/{user_id}"]["get"]["description"]
    assert "permiso global" in paths["/users/{user_id}"]["get"]["description"]
    assert "solo las direcciones propias" in paths["/user-addresses/"]["get"][
        "description"
    ]
    assert "alcance global" in paths[
        "/user-addresses/{user_address_id}"
    ]["patch"]["description"]


def test_roles_document_system_immutability_and_permission_codes() -> None:
    schemas = app.openapi()["components"]["schemas"]
    paths = app.openapi()["paths"]

    assert "inmutable" in schemas["RoleResponse"]["properties"]["isSystem"][
        "description"
    ]
    assert "tabla compartida" in schemas["PermissionResponse"][
        "properties"
    ]["code"]["description"]
    assert "roles del sistema son inmutables" in paths[
        "/roles/{role_id}"
    ]["patch"]["description"]


def test_legacy_user_roles_remain_deprecated_without_stage_four_changes() -> None:
    operations = list(_operations_for_tag("user-roles"))

    assert operations
    assert all(operation["deprecated"] is True for operation in operations)


def test_delete_contracts_return_204_without_content() -> None:
    paths = app.openapi()["paths"]

    assert "content" not in paths["/users/{user_id}"]["delete"]["responses"]["204"]
    assert "content" not in paths[
        "/user-addresses/{user_address_id}"
    ]["delete"]["responses"]["204"]
