from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, computed_field, field_validator, model_validator

from src.core.schema import BaseModel
from src.core.utils.utils import datetime_now


class OrderPeriodStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class OrderPeriodEventType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    CLOSED_EARLY = "closed_early"


def _require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria")

    return value


class OrderPeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    opens_at: datetime
    closes_at: datetime

    _validate_opens_at = field_validator("opens_at")(_require_aware_datetime)
    _validate_closes_at = field_validator("closes_at")(_require_aware_datetime)

    @model_validator(mode="after")
    def validate_interval(self) -> OrderPeriodCreate:
        if self.opens_at >= self.closes_at:
            raise ValueError("La apertura debe ser anterior al cierre")

        return self


class OrderPeriodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    opens_at: datetime | None = None
    closes_at: datetime | None = None

    @field_validator("opens_at", "closes_at")
    @classmethod
    def validate_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            return _require_aware_datetime(value)

        return value

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> OrderPeriodUpdate:
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Los campos enviados no pueden ser nulos")

        return self


class OrderPeriodResponse(BaseModel):
    id: int
    name: str
    opens_at: datetime
    closes_at: datetime
    created_by_user_id: int
    date_added: datetime
    date_updated: datetime | None = None

    @computed_field
    @property
    def status(self) -> OrderPeriodStatus:
        from .rules import resolve_order_period_status

        return resolve_order_period_status(
            self.opens_at,
            self.closes_at,
            datetime_now(),
        )


class OrderPeriodListResponse(BaseModel):
    items: list[OrderPeriodResponse]
    total: int


class OrderPeriodHistoryChange(BaseModel):
    field: str
    old_value: object | None = None
    new_value: object | None = None


class OrderPeriodHistoryResponse(BaseModel):
    id: int
    order_period_id: int
    event: OrderPeriodEventType
    actor_user_id: int
    occurred_at: datetime
    changes: list[OrderPeriodHistoryChange]
