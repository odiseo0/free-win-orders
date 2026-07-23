from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, computed_field, field_validator, model_validator

from src.core.schema import BaseModel, PaginatedResponse
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
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Nombre público que identifica el Pedido.",
        examples=["Pedido agosto 2026"],
    )
    opens_at: datetime = Field(
        description=(
            "Fecha de apertura con zona horaria. Antes de esta fecha el Pedido "
            "permanece en borrador."
        ),
        examples=["2026-08-01T12:00:00Z"],
    )
    closes_at: datetime = Field(
        description=(
            "Fecha de cierre con zona horaria, posterior a la apertura."
        ),
        examples=["2026-08-22T12:00:00Z"],
    )

    _validate_opens_at = field_validator("opens_at")(_require_aware_datetime)
    _validate_closes_at = field_validator("closes_at")(_require_aware_datetime)

    @model_validator(mode="after")
    def validate_interval(self) -> OrderPeriodCreate:
        if self.opens_at >= self.closes_at:
            raise ValueError("La apertura debe ser anterior al cierre")

        return self


class OrderPeriodUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nuevo nombre. Si se omite, conserva el valor actual.",
        examples=["Pedido agosto 2026 — extensión"],
    )
    opens_at: datetime | None = Field(
        default=None,
        description=(
            "Nueva apertura con zona horaria. Solo puede cambiar mientras la regla "
            "temporal del Pedido lo permita."
        ),
        examples=["2026-08-02T12:00:00Z"],
    )
    closes_at: datetime | None = Field(
        default=None,
        description=(
            "Nuevo cierre con zona horaria. No puede enviarse como nulo ni ser "
            "anterior a la apertura."
        ),
        examples=["2026-08-29T12:00:00Z"],
    )

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
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 12,
                    "name": "Pedido agosto 2026",
                    "opensAt": "2026-08-01T12:00:00Z",
                    "closesAt": "2026-08-22T12:00:00Z",
                    "createdByUserId": 3,
                    "dateAdded": "2026-07-25T18:00:00Z",
                    "dateUpdated": None,
                    "status": "open",
                }
            ]
        }
    }

    id: int = Field(description="Identificador del Pedido.")
    name: str = Field(description="Nombre público del Pedido.")
    opens_at: datetime = Field(description="Fecha de apertura con zona horaria.")
    closes_at: datetime = Field(description="Fecha de cierre con zona horaria.")
    created_by_user_id: int = Field(
        description="Usuario administrador que creó el Pedido."
    )
    date_added: datetime = Field(description="Fecha de creación con zona horaria.")
    date_updated: datetime | None = Field(
        default=None,
        description="Última actualización con zona horaria, si ocurrió.",
    )

    @computed_field(
        description=(
            "Estado calculado en servidor con las fechas del Pedido y la hora actual."
        )
    )
    @property
    def status(self) -> OrderPeriodStatus:
        from .rules import resolve_order_period_status

        return resolve_order_period_status(
            self.opens_at,
            self.closes_at,
            datetime_now(),
        )


class OrderPeriodListResponse(PaginatedResponse[OrderPeriodResponse]):
    pass


class OrderPeriodHistoryChange(BaseModel):
    field: str = Field(description="Campo de negocio que cambió.")
    old_value: object | None = Field(
        default=None, description="Valor anterior serializable."
    )
    new_value: object | None = Field(
        default=None, description="Valor nuevo serializable."
    )


class OrderPeriodHistoryResponse(BaseModel):
    id: int = Field(description="Identificador del evento.")
    order_period_id: int = Field(description="Pedido afectado.")
    event: OrderPeriodEventType = Field(description="Tipo de evento registrado.")
    actor_user_id: int = Field(description="Usuario que produjo el evento.")
    occurred_at: datetime = Field(
        description="Fecha del evento con zona horaria."
    )
    changes: list[OrderPeriodHistoryChange] = Field(
        description="Cambios estructurados registrados por el evento."
    )
