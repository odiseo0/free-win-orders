from datetime import datetime, timedelta, timezone

import pytest

from src.api.order_periods.domain import OrderPeriodStatus, resolve_order_period_status


OPENING = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
CLOSING = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (OPENING - timedelta(microseconds=1), OrderPeriodStatus.DRAFT),
        (OPENING, OrderPeriodStatus.OPEN),
        (OPENING + timedelta(microseconds=1), OrderPeriodStatus.OPEN),
        (CLOSING - timedelta(microseconds=1), OrderPeriodStatus.OPEN),
        (CLOSING, OrderPeriodStatus.CLOSED),
        (CLOSING + timedelta(microseconds=1), OrderPeriodStatus.CLOSED),
    ],
)
def test_status_uses_half_open_date_boundaries(
    now: datetime, expected: OrderPeriodStatus
) -> None:
    assert resolve_order_period_status(OPENING, CLOSING, now) is expected


def test_status_recognizes_equivalent_timezone_offsets() -> None:
    venezuela = timezone(timedelta(hours=-4))
    equivalent_opening = OPENING.astimezone(venezuela)

    assert (
        resolve_order_period_status(OPENING, CLOSING, equivalent_opening)
        is OrderPeriodStatus.OPEN
    )


@pytest.mark.parametrize(
    ("opens_at", "closes_at", "now"),
    [
        (OPENING.replace(tzinfo=None), CLOSING, OPENING),
        (OPENING, CLOSING.replace(tzinfo=None), OPENING),
        (OPENING, CLOSING, OPENING.replace(tzinfo=None)),
    ],
)
def test_status_rejects_naive_datetimes(
    opens_at: datetime, closes_at: datetime, now: datetime
) -> None:
    with pytest.raises(ValueError):
        resolve_order_period_status(opens_at, closes_at, now)

