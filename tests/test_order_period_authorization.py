import pytest

from src.api.order_periods.domain import can_read_order_period
from src.api.roles.domain import (
    Actor,
    AuthorizationDecision,
    PermissionCode,
    USER_PERMISSIONS,
    require_permission,
)


ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
USER = Actor(user_id=2, permissions=USER_PERMISSIONS)


@pytest.mark.parametrize(
    "permission",
    [
        PermissionCode.ORDER_PERIODS_READ,
        PermissionCode.ORDER_PERIODS_READ_DRAFTS,
        PermissionCode.ORDER_PERIODS_CREATE,
        PermissionCode.ORDER_PERIODS_UPDATE,
        PermissionCode.ORDER_PERIODS_CLOSE,
    ],
)
def test_admin_has_every_order_period_permission(permission: PermissionCode) -> None:
    assert require_permission(ADMIN, permission) is AuthorizationDecision.ALLOW


def test_user_can_read_order_periods() -> None:
    assert (
        require_permission(USER, PermissionCode.ORDER_PERIODS_READ)
        is AuthorizationDecision.ALLOW
    )


@pytest.mark.parametrize(
    "permission",
    [
        PermissionCode.ORDER_PERIODS_READ_DRAFTS,
        PermissionCode.ORDER_PERIODS_CREATE,
        PermissionCode.ORDER_PERIODS_UPDATE,
        PermissionCode.ORDER_PERIODS_CLOSE,
    ],
)
def test_user_cannot_administer_order_periods(permission: PermissionCode) -> None:
    assert require_permission(USER, permission) is AuthorizationDecision.FORBIDDEN


def test_admin_can_read_a_draft() -> None:
    assert can_read_order_period(ADMIN, is_draft=True) is AuthorizationDecision.ALLOW


def test_user_can_read_a_published_period() -> None:
    assert can_read_order_period(USER, is_draft=False) is AuthorizationDecision.ALLOW


def test_draft_is_hidden_from_a_regular_user() -> None:
    assert can_read_order_period(USER, is_draft=True) is AuthorizationDecision.HIDDEN
