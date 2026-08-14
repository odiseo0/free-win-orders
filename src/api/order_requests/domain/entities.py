from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import ClassVar

from pydantic import Field, computed_field, field_validator, model_validator

from src.core.schema import BaseModel, PaginatedResponse

MONEY_QUANTUM = Decimal("0.01")
DEFAULT_TAX_RATE = Decimal("0.16")
DEFAULT_SHIPPING_UNIT_PRICE = Decimal("5.00")


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_default_tax_unit_price(card_unit_price: Decimal) -> Decimal:
    return quantize_usd(card_unit_price * DEFAULT_TAX_RATE)


class OrderRequestStatus(StrEnum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class OrderRequestEventType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ITEM_ADDED = "item_added"
    ITEM_UPDATED = "item_updated"
    ITEM_REMOVED = "item_removed"
    ITEM_RESTORED = "item_restored"


class OrderRequestItemCreate(BaseModel):
    card_listing_id: int = Field(
        gt=0,
        description="Identificador de la publicación de carta que se desea comprar.",
        examples=[145],
    )
    requested_quantity: int = Field(
        gt=0,
        description="Cantidad de copias solicitadas por el usuario.",
        examples=[2],
    )


class OrderRequestCreate(BaseModel):
    order_period_id: int = Field(
        gt=0,
        description="Pedido abierto dentro del cual se envía la Orden.",
        examples=[12],
    )
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Nota opcional compartida entre el usuario y los administradores.",
        examples=["Priorizar cartas en condición Near Mint."],
    )
    items: list[OrderRequestItemCreate] = Field(
        min_length=1,
        description="Cartas solicitadas; una publicación no puede repetirse.",
    )

    @model_validator(mode="after")
    def reject_duplicate_listings(self) -> OrderRequestCreate:
        listing_ids = [item.card_listing_id for item in self.items]

        if len(listing_ids) != len(set(listing_ids)):
            raise ValueError("Una publicación no puede repetirse en la misma Orden")

        return self


class OrderRequestUpdate(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Nueva nota compartida. Un valor nulo elimina la nota existente.",
        examples=["Aceptar también cartas Lightly Played."],
    )

    @model_validator(mode="after")
    def require_note_field(self) -> OrderRequestUpdate:
        if "note" not in self.model_fields_set:
            raise ValueError("Debe enviarse la nota")

        return self


class OrderRequestItemUpdate(BaseModel):
    model_config: ClassVar = {"extra": "forbid"}

    requested_quantity: int | None = Field(
        default=None,
        gt=0,
        description="Nueva cantidad solicitada. Si se omite, conserva el valor actual.",
        examples=[3],
    )
    agreed_quantity: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Cantidad que se intentará comprar. No puede superar la solicitada; "
            "si se omite, conserva el valor actual."
        ),
        examples=[2],
    )

    @model_validator(mode="after")
    def require_non_null_update(self) -> OrderRequestItemUpdate:
        if not self.model_fields_set:
            raise ValueError("Debe enviarse al menos una cantidad")

        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Las cantidades enviadas no pueden ser nulas")

        return self


class OrderRequestItemPricingUpdate(BaseModel):
    model_config: ClassVar = {"extra": "forbid"}

    card_unit_price: Decimal = Field(
        ge=0,
        description="Precio definitivo de una copia de la carta, en USD.",
        examples=["3.50"],
    )
    shipping_unit_price: Decimal = Field(
        default=DEFAULT_SHIPPING_UNIT_PRICE,
        ge=0,
        description=(
            "Parte del envío asignada a una copia, en USD. Si se omite, usa "
            "USD 5,00."
        ),
        examples=["5.00"],
    )
    tax_unit_price: Decimal = Field(
        default_factory=Decimal,
        ge=0,
        description=(
            "Parte de impuestos asignada a una copia, en USD. Si se omite, se "
            "calcula como 16 % del precio unitario de la carta."
        ),
        examples=["0.56"],
    )

    @field_validator(
        "card_unit_price",
        "shipping_unit_price",
        "tax_unit_price",
        mode="after",
    )
    @classmethod
    def normalize_money(cls, value: Decimal) -> Decimal:
        return quantize_usd(value)

    @model_validator(mode="after")
    def apply_default_tax(self) -> OrderRequestItemPricingUpdate:
        if "tax_unit_price" not in self.model_fields_set:
            self.tax_unit_price = calculate_default_tax_unit_price(
                self.card_unit_price
            )

        return self

    @computed_field(
        description=(
            "Suma calculada en servidor de carta, envío e impuesto por cada copia."
        )
    )
    @property
    def final_unit_price(self) -> Decimal:
        return quantize_usd(
            self.card_unit_price + self.shipping_unit_price + self.tax_unit_price
        )


class OrderRequestItemResponse(BaseModel):
    id: int = Field(description="Identificador del ítem dentro de la Orden.")
    card_listing_id: int = Field(description="Publicación de carta seleccionada.")
    card_name: str = Field(description="Nombre de la carta conservado como snapshot.")
    card_set: str = Field(description="Set conservado como snapshot.")
    card_code: str = Field(description="Código de carta conservado como snapshot.")
    rarity: str = Field(description="Rareza conservada como snapshot.")
    condition: str = Field(description="Condición conservada como snapshot.")
    estimated_unit_price: Decimal = Field(
        description="Precio unitario estimado al enviar la Orden, en USD."
    )
    requested_quantity: int = Field(description="Cantidad solicitada por el usuario.")
    agreed_quantity: int = Field(description="Cantidad acordada para intentar comprar.")
    card_unit_price: Decimal | None = Field(
        default=None,
        description="Precio definitivo de la carta en USD; nulo hasta su revisión.",
    )
    shipping_unit_price: Decimal | None = Field(
        default=None,
        description=(
            "Envío unitario en USD; comienza en USD 5,00 y puede ajustarse "
            "durante la revisión."
        ),
    )
    tax_unit_price: Decimal | None = Field(
        default=None,
        description=(
            "Impuesto unitario en USD; comienza en 16 % del precio estimado y "
            "puede ajustarse durante la revisión."
        ),
    )
    removed_at: datetime | None = Field(
        default=None,
        description="Fecha con zona horaria del retiro lógico; nula si sigue activo.",
    )
    removed_by_user_id: int | None = Field(
        default=None,
        description="Usuario que retiró el ítem; nulo mientras siga activo.",
    )
    date_added: datetime = Field(description="Fecha de creación con zona horaria.")
    date_updated: datetime | None = Field(
        default=None,
        description="Última actualización con zona horaria, si ocurrió.",
    )

    @computed_field(
        description=(
            "Precio unitario definitivo calculado; nulo mientras falte un componente."
        )
    )
    @property
    def final_unit_price(self) -> Decimal | None:
        prices = (
            self.card_unit_price,
            self.shipping_unit_price,
            self.tax_unit_price,
        )

        if any(price is None for price in prices):
            return None

        total = sum((price for price in prices if price is not None), Decimal())

        return quantize_usd(total)

    @computed_field(
        description=(
            "Total acordado del ítem; nulo si faltan precios o el ítem está retirado."
        )
    )
    @property
    def agreed_total(self) -> Decimal | None:
        if self.final_unit_price is None or self.removed_at is not None:
            return None

        return quantize_usd(self.final_unit_price * self.agreed_quantity)


class OrderRequestResponse(BaseModel):
    model_config: ClassVar = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 41,
                    "orderPeriodId": 12,
                    "createdByUserId": 7,
                    "status": "submitted",
                    "note": "Priorizar cartas en condición Near Mint.",
                    "currency": "USD",
                    "cancelledAt": None,
                    "cancelledByUserId": None,
                    "items": [
                        {
                            "id": 93,
                            "cardListingId": 145,
                            "cardName": "Dark Magician",
                            "cardSet": "Legend of Blue Eyes White Dragon",
                            "cardCode": "LOB-005",
                            "rarity": "Ultra Rare",
                            "condition": "Near Mint",
                            "estimatedUnitPrice": "3.50",
                            "requestedQuantity": 2,
                            "agreedQuantity": 0,
                            "cardUnitPrice": None,
                            "shippingUnitPrice": None,
                            "taxUnitPrice": None,
                            "removedAt": None,
                            "removedByUserId": None,
                            "dateAdded": "2026-08-03T15:30:00Z",
                            "dateUpdated": None,
                            "finalUnitPrice": None,
                            "agreedTotal": None,
                        }
                    ],
                    "dateAdded": "2026-08-03T15:30:00Z",
                    "dateUpdated": None,
                    "agreedTotal": None,
                }
            ]
        }
    }

    id: int = Field(description="Identificador de la Orden.")
    order_period_id: int = Field(description="Pedido al que pertenece la Orden.")
    created_by_user_id: int = Field(description="Usuario propietario de la Orden.")
    status: OrderRequestStatus = Field(
        description="Estado actual de revisión de la Orden."
    )
    note: str | None = Field(
        default=None,
        description="Nota compartida; nula cuando no se ha registrado una.",
    )
    currency: str = Field(
        default="USD",
        description="Moneda ISO 4217 usada por todos los importes de la Orden.",
        examples=["USD"],
    )
    cancelled_at: datetime | None = Field(
        default=None,
        description="Fecha con zona horaria de cancelación; nula si no está cancelada.",
    )
    cancelled_by_user_id: int | None = Field(
        default=None,
        description="Usuario que canceló la Orden; nulo si no está cancelada.",
    )
    items: list[OrderRequestItemResponse] = Field(
        description="Ítems activos y retirados que preservan sus snapshots."
    )
    date_added: datetime = Field(description="Fecha de envío con zona horaria.")
    date_updated: datetime | None = Field(
        default=None,
        description="Última actualización con zona horaria, si ocurrió.",
    )

    @computed_field(
        description=(
            "Suma de ítems activos con precios completos; nula si todavía no puede "
            "calcularse."
        )
    )
    @property
    def agreed_total(self) -> Decimal | None:
        active_items = [item for item in self.items if item.removed_at is None]
        totals = [item.agreed_total for item in active_items]

        if not active_items or any(total is None for total in totals):
            return None

        order_total = sum((total for total in totals if total is not None), Decimal())

        return quantize_usd(order_total)


class OrderRequestListResponse(PaginatedResponse[OrderRequestResponse]):
    pass


class OrderRequestHistoryChange(BaseModel):
    field: str = Field(description="Campo de negocio que cambió.")
    old_value: object | None = Field(
        default=None, description="Valor anterior serializable."
    )
    new_value: object | None = Field(
        default=None, description="Valor nuevo serializable."
    )


class OrderRequestHistoryResponse(BaseModel):
    id: int = Field(description="Identificador del evento.")
    order_request_id: int = Field(description="Orden afectada.")
    event: OrderRequestEventType = Field(description="Tipo de evento registrado.")
    actor_user_id: int = Field(description="Usuario que produjo el evento.")
    occurred_at: datetime = Field(description="Fecha del evento con zona horaria.")
    changes: list[OrderRequestHistoryChange] = Field(
        description="Cambios estructurados registrados por el evento."
    )
