from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import Field, computed_field, field_validator, model_validator

from src.core.schema import BaseModel

MONEY_QUANTUM = Decimal("0.01")


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


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
    card_listing_id: int = Field(gt=0)
    requested_quantity: int = Field(gt=0)


class OrderRequestCreate(BaseModel):
    order_period_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=2000)
    items: list[OrderRequestItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_listings(self) -> OrderRequestCreate:
        listing_ids = [item.card_listing_id for item in self.items]

        if len(listing_ids) != len(set(listing_ids)):
            raise ValueError("Una publicación no puede repetirse en la misma Orden")

        return self


class OrderRequestUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_note_field(self) -> OrderRequestUpdate:
        if "note" not in self.model_fields_set:
            raise ValueError("Debe enviarse la nota")

        return self


class OrderRequestItemUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    requested_quantity: int | None = Field(default=None, gt=0)
    agreed_quantity: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_non_null_update(self) -> OrderRequestItemUpdate:
        if not self.model_fields_set:
            raise ValueError("Debe enviarse al menos una cantidad")

        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Las cantidades enviadas no pueden ser nulas")

        return self


class OrderRequestItemPricingUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    card_unit_price: Decimal = Field(ge=0)
    shipping_unit_price: Decimal = Field(ge=0)
    tax_unit_price: Decimal = Field(ge=0)

    @field_validator(
        "card_unit_price",
        "shipping_unit_price",
        "tax_unit_price",
        mode="after",
    )
    @classmethod
    def normalize_money(cls, value: Decimal) -> Decimal:
        return quantize_usd(value)

    @computed_field
    @property
    def final_unit_price(self) -> Decimal:
        return quantize_usd(
            self.card_unit_price + self.shipping_unit_price + self.tax_unit_price
        )


class OrderRequestItemResponse(BaseModel):
    id: int
    card_listing_id: int
    card_name: str
    card_set: str
    card_code: str
    rarity: str
    condition: str
    estimated_unit_price: Decimal
    requested_quantity: int
    agreed_quantity: int
    card_unit_price: Decimal | None = None
    shipping_unit_price: Decimal | None = None
    tax_unit_price: Decimal | None = None
    removed_at: datetime | None = None
    removed_by_user_id: int | None = None
    date_added: datetime
    date_updated: datetime | None = None

    @computed_field
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

    @computed_field
    @property
    def agreed_total(self) -> Decimal | None:
        if self.final_unit_price is None or self.removed_at is not None:
            return None

        return quantize_usd(self.final_unit_price * self.agreed_quantity)


class OrderRequestResponse(BaseModel):
    id: int
    order_period_id: int
    created_by_user_id: int
    status: OrderRequestStatus
    note: str | None = None
    currency: str = "USD"
    cancelled_at: datetime | None = None
    cancelled_by_user_id: int | None = None
    items: list[OrderRequestItemResponse]
    date_added: datetime
    date_updated: datetime | None = None

    @computed_field
    @property
    def agreed_total(self) -> Decimal | None:
        active_items = [item for item in self.items if item.removed_at is None]
        totals = [item.agreed_total for item in active_items]

        if not active_items or any(total is None for total in totals):
            return None

        order_total = sum((total for total in totals if total is not None), Decimal())

        return quantize_usd(order_total)


class OrderRequestListResponse(BaseModel):
    items: list[OrderRequestResponse]
    total: int


class OrderRequestHistoryChange(BaseModel):
    field: str
    old_value: object | None = None
    new_value: object | None = None


class OrderRequestHistoryResponse(BaseModel):
    id: int
    order_request_id: int
    event: OrderRequestEventType
    actor_user_id: int
    occurred_at: datetime
    changes: list[OrderRequestHistoryChange]


class OrderRequestErrorResponse(BaseModel):
    detail: str
