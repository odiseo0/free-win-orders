from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.api.order_periods.domain import (
    OrderPeriodCreate,
    OrderPeriodEventType,
    OrderPeriodHistoryResponse,
    OrderPeriodResponse,
    OrderPeriodStatus,
    OrderPeriodUpdate,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def valid_create_payload() -> dict[str, object]:
    return {
        "name": "Pedido agosto 2026",
        "opensAt": NOW + timedelta(days=1),
        "closesAt": NOW + timedelta(days=15),
    }


def test_order_period_create_accepts_a_scheduled_period() -> None:
    contract = OrderPeriodCreate.model_validate(valid_create_payload())

    assert contract.name == "Pedido agosto 2026"
    assert contract.opens_at == NOW + timedelta(days=1)
    assert contract.closes_at == NOW + timedelta(days=15)


def test_order_period_create_strips_name_whitespace() -> None:
    payload = valid_create_payload()
    payload["name"] = "  Pedido agosto 2026  "

    contract = OrderPeriodCreate.model_validate(payload)

    assert contract.name == "Pedido agosto 2026"


@pytest.mark.parametrize("missing_field", ["name", "opensAt", "closesAt"])
def test_order_period_create_requires_every_field(missing_field: str) -> None:
    payload = valid_create_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError):
        OrderPeriodCreate.model_validate(payload)


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_order_period_create_rejects_invalid_names(name: str) -> None:
    payload = valid_create_payload()
    payload["name"] = name

    with pytest.raises(ValidationError):
        OrderPeriodCreate.model_validate(payload)


@pytest.mark.parametrize("field", ["opensAt", "closesAt"])
def test_order_period_create_rejects_naive_datetimes(field: str) -> None:
    payload = valid_create_payload()
    payload[field] = datetime(2026, 7, 23, 12, 0)

    with pytest.raises(ValidationError):
        OrderPeriodCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("opens_at", "closes_at"),
    [
        (NOW + timedelta(days=1), NOW + timedelta(days=1)),
        (NOW + timedelta(days=2), NOW + timedelta(days=1)),
    ],
)
def test_order_period_create_rejects_an_invalid_interval(
    opens_at: datetime, closes_at: datetime
) -> None:
    payload = valid_create_payload()
    payload.update({"opensAt": opens_at, "closesAt": closes_at})

    with pytest.raises(ValidationError):
        OrderPeriodCreate.model_validate(payload)


def test_order_period_update_distinguishes_omitted_fields() -> None:
    contract = OrderPeriodUpdate.model_validate({"name": "Nuevo nombre"})

    assert contract.model_fields_set == {"name"}
    assert contract.opens_at is None
    assert contract.closes_at is None


def test_order_period_update_rejects_explicit_nulls() -> None:
    with pytest.raises(ValidationError):
        OrderPeriodUpdate.model_validate({"closesAt": None})


def test_order_period_response_derives_status_and_serializes_camel_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.api.order_periods.domain.entities.datetime_now", lambda: NOW
    )
    response = OrderPeriodResponse.model_validate(
        {
            "id": 7,
            "name": "Pedido inmediato",
            "opensAt": NOW,
            "closesAt": NOW + timedelta(days=14),
            "createdByUserId": 3,
            "dateAdded": NOW - timedelta(minutes=1),
            "dateUpdated": None,
        }
    )

    serialized = response.model_dump(mode="json", by_alias=True)

    assert serialized == {
        "id": 7,
        "name": "Pedido inmediato",
        "opensAt": NOW.isoformat().replace("+00:00", "Z"),
        "closesAt": (NOW + timedelta(days=14)).isoformat().replace("+00:00", "Z"),
        "status": "open",
        "createdByUserId": 3,
        "dateAdded": (NOW - timedelta(minutes=1)).isoformat().replace(
            "+00:00", "Z"
        ),
        "dateUpdated": None,
    }


def test_order_period_response_reads_orm_attributes_without_manual_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.api.order_periods.domain.entities.datetime_now", lambda: NOW
    )
    period = SimpleNamespace(
        id=7,
        name="Pedido inmediato",
        opens_at=NOW,
        closes_at=NOW + timedelta(days=14),
        created_by_user_id=3,
        date_added=NOW - timedelta(minutes=1),
        date_updated=None,
    )

    response = OrderPeriodResponse.model_validate(period)

    assert response.status is OrderPeriodStatus.OPEN
    assert response.model_dump(by_alias=True)["createdByUserId"] == 3


def test_history_response_exposes_structured_changes_without_actor_details() -> None:
    history = OrderPeriodHistoryResponse.model_validate(
        {
            "id": 9,
            "orderPeriodId": 7,
            "event": OrderPeriodEventType.UPDATED,
            "actorUserId": 3,
            "occurredAt": NOW,
            "changes": [
                {
                    "field": "closesAt",
                    "oldValue": "2026-08-01T12:00:00Z",
                    "newValue": "2026-08-08T12:00:00Z",
                }
            ],
        }
    )

    serialized = history.model_dump(mode="json", by_alias=True)

    assert serialized["event"] == "updated"
    assert serialized["actorUserId"] == 3
    assert serialized["changes"][0]["field"] == "closesAt"
    assert "actor" not in serialized
    assert "session" not in serialized
