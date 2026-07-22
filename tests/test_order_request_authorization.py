from src.api.order_requests.domain import can_access_order_request
from src.api.roles.domain import (
    Actor,
    AuthorizationDecision,
    PermissionCode,
    USER_PERMISSIONS,
    require_permission,
)


ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
USER = Actor(user_id=2, permissions=USER_PERMISSIONS)


def test_user_has_order_request_self_permissions() -> None:
    for permission in (
        PermissionCode.ORDER_REQUESTS_READ_SELF,
        PermissionCode.ORDER_REQUESTS_CREATE_SELF,
        PermissionCode.ORDER_REQUESTS_UPDATE_SELF,
    ):
        assert require_permission(USER, permission) is AuthorizationDecision.ALLOW


def test_user_does_not_have_admin_order_request_permissions() -> None:
    for permission in (
        PermissionCode.ORDER_REQUESTS_READ_ANY,
        PermissionCode.ORDER_REQUESTS_UPDATE_ANY,
        PermissionCode.ORDER_REQUESTS_REVIEW,
    ):
        assert require_permission(USER, permission) is AuthorizationDecision.FORBIDDEN


def test_owner_can_access_own_order_request() -> None:
    assert (
        can_access_order_request(USER, owner_user_id=USER.user_id, write=True)
        is AuthorizationDecision.ALLOW
    )


def test_foreign_order_request_is_hidden_from_user() -> None:
    assert (
        can_access_order_request(USER, owner_user_id=99, write=False)
        is AuthorizationDecision.HIDDEN
    )


def test_admin_can_read_and_update_any_order_request() -> None:
    assert (
        can_access_order_request(ADMIN, owner_user_id=99, write=False)
        is AuthorizationDecision.ALLOW
    )
    assert (
        can_access_order_request(ADMIN, owner_user_id=99, write=True)
        is AuthorizationDecision.ALLOW
    )
