import pytest

from src.api.roles.domain import (
    Actor,
    AuthorizationDecision,
    PermissionCode,
    USER_PERMISSIONS,
    require_owner_or_permission,
    require_permission,
)


ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
USER = Actor(user_id=2, permissions=USER_PERMISSIONS)


@pytest.mark.parametrize("permission", list(PermissionCode))
def test_admin_has_every_permission(permission: PermissionCode) -> None:
    assert require_permission(ADMIN, permission) is AuthorizationDecision.ALLOW


@pytest.mark.parametrize("permission", list(USER_PERMISSIONS))
def test_user_has_only_basic_permissions(permission: PermissionCode) -> None:
    assert require_permission(USER, permission) is AuthorizationDecision.ALLOW


@pytest.mark.parametrize(
    "permission",
    [
        PermissionCode.USERS_READ_ANY,
        PermissionCode.USERS_UPDATE_ANY,
        PermissionCode.USERS_DELETE_ANY,
        PermissionCode.USERS_ASSIGN_ROLE,
        PermissionCode.ADDRESSES_READ_ANY,
        PermissionCode.ORDER_PERIODS_CREATE,
        PermissionCode.ORDER_PERIODS_UPDATE,
        PermissionCode.ORDER_PERIODS_CLOSE,
        PermissionCode.ROLES_READ,
        PermissionCode.ROLES_CREATE,
        PermissionCode.ROLES_UPDATE,
        PermissionCode.ROLES_DELETE,
        PermissionCode.ROLES_ASSIGN_PERMISSIONS,
        PermissionCode.PERMISSIONS_READ,
    ],
)
def test_user_does_not_have_administrative_permissions(
    permission: PermissionCode,
) -> None:
    assert require_permission(USER, permission) is AuthorizationDecision.FORBIDDEN


def test_owner_policy_allows_the_owner() -> None:
    decision = require_owner_or_permission(
        USER,
        USER.user_id,
        own_permission=PermissionCode.USERS_READ_SELF,
        any_permission=PermissionCode.USERS_READ_ANY,
    )
    assert decision is AuthorizationDecision.ALLOW


def test_owner_policy_hides_another_users_resource() -> None:
    decision = require_owner_or_permission(
        USER,
        999,
        own_permission=PermissionCode.USERS_READ_SELF,
        any_permission=PermissionCode.USERS_READ_ANY,
    )
    assert decision is AuthorizationDecision.HIDDEN


def test_general_permission_allows_access_to_any_owner() -> None:
    decision = require_owner_or_permission(
        ADMIN,
        999,
        own_permission=PermissionCode.USERS_READ_SELF,
        any_permission=PermissionCode.USERS_READ_ANY,
    )
    assert decision is AuthorizationDecision.ALLOW
