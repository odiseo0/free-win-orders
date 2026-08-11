import pytest
from pydantic import ValidationError

from src.api.roles.domain import PermissionCode, RolePermissionsUpdate
from src.api.users.domain import UserCreate, UserResponse, UserUpdate


def test_registration_rejects_role_escalation() -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "firstName": "Yugi",
                "lastName": "Muto",
                "email": "yugi@example.com",
                "password": "millennium-puzzle",
                "roleId": 1,
            }
        )


def test_regular_update_has_no_role_field() -> None:
    update = UserUpdate.model_validate({"roleId": 99, "alias": "King of Games"})
    assert "role_id" not in update.model_fields_set


def test_user_response_never_exposes_password() -> None:
    response = UserResponse.model_validate(
        {
            "id": 1,
            "roleId": 2,
            "roleName": "User",
            "firstName": "Yugi",
        }
    )
    assert "password" not in response.model_dump()


def test_permission_contract_rejects_unknown_codes() -> None:
    with pytest.raises(ValidationError):
        RolePermissionsUpdate.model_validate({"permissions": ["catalog.publish"]})


def test_permission_contract_accepts_controlled_codes() -> None:
    contract = RolePermissionsUpdate(
        permissions=[PermissionCode.USERS_READ_SELF, PermissionCode.ORDER_PERIODS_READ]
    )
    assert contract.permissions == [
        PermissionCode.USERS_READ_SELF,
        PermissionCode.ORDER_PERIODS_READ,
    ]
