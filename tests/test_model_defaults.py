from datetime import datetime, timedelta, timezone

from src.api.order_periods.repository import OrderPeriod, OrderPeriodHistory
from src.api.roles.repository import Permission, Role
from src.api.users.repository import UserRole


def test_date_updated_is_optional_when_constructing_models() -> None:
    permission = Permission(code="cards.read", description="Permite leer cartas.")
    role = Role(name="User", description=None, is_system=True)
    bridge = UserRole(role_id=1)

    assert permission.date_updated is None
    assert role.date_updated is None
    assert bridge.date_updated is None


def test_order_period_models_have_safe_construction_defaults() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    period = OrderPeriod(
        name="Pedido agosto 2026",
        opens_at=now,
        closes_at=now + timedelta(days=14),
        created_by_user_id=1,
    )
    history = OrderPeriodHistory(
        order_period_id=1,
        event="created",
        actor_user_id=1,
        occurred_at=now,
        changes=[],
    )

    assert period.date_updated is None
    assert history.changes == []
