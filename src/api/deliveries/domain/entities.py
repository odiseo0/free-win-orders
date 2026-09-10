from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from pydantic import Field, field_validator, model_validator

from src.core.schema import BaseModel


class DeliveryStageScope(StrEnum):
    INTERNATIONAL = "international"
    NATIONAL = "national"
    PICKUP = "pickup"


class DeliveryStageKind(StrEnum):
    PROGRESS = "progress"
    EXCEPTION = "exception"


class ShipmentKind(StrEnum):
    INTERNATIONAL = "international"
    NATIONAL = "national"


class DeliveryMethod(StrEnum):
    PICKUP = "pickup"
    NATIONAL_SHIPPING = "national_shipping"


class DeliveryEventSource(StrEnum):
    ADMIN = "admin"
    SYSTEM = "system"
    CARRIER = "carrier"


class NationalCarrier(StrEnum):
    ZOOM = "zoom"
    MRW = "mrw"


class ShippingCostPayer(StrEnum):
    FREE_WIN = "free_win"
    RECIPIENT = "recipient"


class DeliveryStageCreate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    scope: DeliveryStageScope
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    name: str = Field(min_length=1, max_length=100)
    position: int = Field(ge=0)
    kind: DeliveryStageKind = DeliveryStageKind.PROGRESS
    is_terminal: bool = False


class DeliveryStageUpdate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=100)
    position: int | None = Field(default=None, ge=0)
    kind: DeliveryStageKind | None = None
    is_terminal: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> DeliveryStageUpdate:
        if not self.model_fields_set:
            raise ValueError("Debe enviarse al menos un cambio")

        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Los campos enviados no pueden ser nulos")

        return self


class DeliveryStageResponse(BaseModel):
    id: int
    scope: DeliveryStageScope
    key: str
    name: str
    position: int
    kind: DeliveryStageKind
    is_terminal: bool
    is_active: bool


class ShipmentItemQuantity(BaseModel):
    order_request_item_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class ShipmentOrderAllocation(BaseModel):
    order_request_id: int = Field(gt=0)
    items: list[ShipmentItemQuantity] | None = None

    @field_validator("items")
    @classmethod
    def reject_empty_items(
        cls, value: list[ShipmentItemQuantity] | None
    ) -> list[ShipmentItemQuantity] | None:
        if value == []:
            raise ValueError("Usa null para asignar toda la Orden")

        if value is not None:
            ids = [item.order_request_item_id for item in value]

            if len(ids) != len(set(ids)):
                raise ValueError("Un ítem no puede repetirse")

        return value


class InternationalShipmentCreate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    order_period_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    reference: str | None = Field(default=None, max_length=150)
    external_references: list[str] = Field(default_factory=list, max_length=20)
    allocations: list[ShipmentOrderAllocation] = Field(min_length=1)

    @field_validator("allocations")
    @classmethod
    def reject_duplicate_orders(
        cls, value: list[ShipmentOrderAllocation]
    ) -> list[ShipmentOrderAllocation]:
        ids = [allocation.order_request_id for allocation in value]

        if len(ids) != len(set(ids)):
            raise ValueError("Una Orden no puede repetirse")

        return value


class InternationalShipmentUpdate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=150)
    reference: str | None = Field(default=None, max_length=150)
    external_references: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def require_change(self) -> InternationalShipmentUpdate:
        if not self.model_fields_set:
            raise ValueError("Debe enviarse al menos un cambio")

        return self


class DeliveryEventCreate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    stage_key: str = Field(min_length=1, max_length=50)
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)
    correction_of_event_id: int | None = Field(default=None, gt=0)
    correction_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_correction(self) -> DeliveryEventCreate:
        paired = self.correction_of_event_id is not None

        if paired != (self.correction_reason is not None):
            raise ValueError("Una corrección requiere evento y motivo")

        if self.occurred_at is not None and self.occurred_at.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria")

        return self


class DeliveryEventResponse(BaseModel):
    id: int
    stage_id: int | None
    stage_key: str | None
    stage_name: str | None
    source: DeliveryEventSource
    actor_user_id: int | None
    occurred_at: datetime
    recorded_at: datetime
    note: str | None
    raw_status: str | None
    correction_of_event_id: int | None
    correction_reason: str | None


class ShipmentAllocationResponse(BaseModel):
    order_request_id: int
    order_request_item_id: int
    quantity: int


class InternationalShipmentResponse(BaseModel):
    id: int
    order_period_id: int
    name: str
    reference: str | None
    external_references: list[str]
    current_stage: DeliveryStageResponse
    allocations: list[ShipmentAllocationResponse]
    events: list[DeliveryEventResponse]
    date_added: datetime
    date_updated: datetime | None


class DeliveryPreferenceUpdate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    method: DeliveryMethod
    user_address_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_address(self) -> DeliveryPreferenceUpdate:
        has_address = self.user_address_id is not None

        if self.method is DeliveryMethod.NATIONAL_SHIPPING and not has_address:
            raise ValueError("El envío nacional requiere una dirección")

        if self.method is DeliveryMethod.PICKUP and has_address:
            raise ValueError("El retiro no usa una dirección")

        return self


class DeliveryPreferenceResponse(BaseModel):
    method: DeliveryMethod
    user_address_id: int | None
    date_updated: datetime | None


class FulfillmentCreate(BaseModel):
    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}

    carrier: NationalCarrier | None = None
    tracking_number: str | None = Field(default=None, min_length=1, max_length=100)
    shipping_cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    cost_payer: ShippingCostPayer | None = None

    @model_validator(mode="after")
    def validate_cost(self) -> FulfillmentCreate:
        if (self.shipping_cost is None) != (self.cost_payer is None):
            raise ValueError("El costo y su responsable deben enviarse juntos")

        return self


class FulfillmentResponse(BaseModel):
    id: int
    order_request_id: int
    method: DeliveryMethod
    current_stage: DeliveryStageResponse
    carrier: NationalCarrier | None
    tracking_number: str | None
    shipping_cost: Decimal | None
    currency: str | None
    cost_payer: ShippingCostPayer | None
    recipient_snapshot: dict[str, object] | None
    address_snapshot: dict[str, object] | None
    last_checked_at: datetime | None
    next_check_at: datetime | None
    has_tracking_error: bool
    needs_review: bool
    events: list[DeliveryEventResponse]
    date_added: datetime
    date_updated: datetime | None


class TrackingItemResponse(BaseModel):
    order_request_item_id: int
    agreed_quantity: int
    purchased_quantity: int
    pending_quantity: int


class InternationalTrackingSummary(BaseModel):
    stage_key: str
    stage_name: str
    is_partial: bool
    purchasing_finalized: bool


class OrderTrackingResponse(BaseModel):
    order_request_id: int
    is_paid: bool
    paid_at: datetime | None
    items: list[TrackingItemResponse]
    international_summary: InternationalTrackingSummary
    international_shipments: list[InternationalShipmentResponse]
    preference: DeliveryPreferenceResponse | None
    fulfillment: FulfillmentResponse | None
