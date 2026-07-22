from datetime import datetime

from src.api.roles.domain import (
    Actor,
    AuthorizationDecision,
    PermissionCode,
)

from .entities import OrderPeriodStatus


def _ensure_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Las fechas deben incluir zona horaria")


def resolve_order_period_status(
    opens_at: datetime,
    closes_at: datetime,
    now: datetime,
) -> OrderPeriodStatus:
    _ensure_aware(opens_at)
    _ensure_aware(closes_at)
    _ensure_aware(now)

    if now < opens_at:
        return OrderPeriodStatus.DRAFT
    if now < closes_at:
        return OrderPeriodStatus.OPEN

    return OrderPeriodStatus.CLOSED


def can_read_order_period(actor: Actor, *, is_draft: bool) -> AuthorizationDecision:
    if PermissionCode.ORDER_PERIODS_READ not in actor.permissions:
        return AuthorizationDecision.FORBIDDEN

    if is_draft and PermissionCode.ORDER_PERIODS_READ_DRAFTS not in actor.permissions:
        return AuthorizationDecision.HIDDEN

    return AuthorizationDecision.ALLOW
