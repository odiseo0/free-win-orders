from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.core.db import DAO, StrategyOptions
from src.core.utils.utils import Empty, EmptyType

from .models import (
    DeliveryEvent,
    DeliveryFulfillment,
    DeliveryPreference,
    DeliveryShipment,
    DeliveryShipmentAllocation,
    DeliveryStage,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DeliveryStageDAO(DAO[DeliveryStage, BaseModel, BaseModel]):
    async def get_by_key(
        self, db: AsyncSession, *, scope: str, key: str, active_only: bool = False
    ) -> DeliveryStage | EmptyType:
        statement = select(DeliveryStage).where(
            DeliveryStage.scope == scope, DeliveryStage.key == key
        )
        if active_only:
            statement = statement.where(DeliveryStage.is_active.is_(True))
        stage = await db.scalar(statement)
        return stage if stage is not None else Empty

    async def list_for_scope(
        self, db: AsyncSession, scope: str | None = None
    ) -> list[DeliveryStage]:
        statement = select(DeliveryStage)
        if scope is not None:
            statement = statement.where(DeliveryStage.scope == scope)
        statement = statement.order_by(DeliveryStage.scope, DeliveryStage.position)
        return list((await db.execute(statement)).scalars().all())


class DeliveryShipmentDAO(DAO[DeliveryShipment, BaseModel, BaseModel]):
    OPTIONS: ClassVar[list] = [
        selectinload(DeliveryShipment.allocations),
        selectinload(DeliveryShipment.events),
    ]

    async def get_full(
        self, db: AsyncSession, shipment_id: int, *, for_update: bool = False
    ) -> DeliveryShipment | EmptyType:
        statement = (
            select(DeliveryShipment)
            .where(DeliveryShipment.id == shipment_id)
            .options(*self.OPTIONS)
        )

        if for_update:
            statement = statement.with_for_update(of=DeliveryShipment)

        shipment = (await db.execute(statement)).unique().scalar_one_or_none()

        return shipment if shipment is not None else Empty

    async def list_international(
        self, db: AsyncSession, order_period_id: int
    ) -> list[DeliveryShipment]:
        statement = (
            select(DeliveryShipment)
            .where(
                DeliveryShipment.kind == "international",
                DeliveryShipment.order_period_id == order_period_id,
            )
            .options(*self.OPTIONS)
            .order_by(DeliveryShipment.date_added.desc())
        )

        return list((await db.execute(statement)).unique().scalars().all())

    async def list_for_order(
        self, db: AsyncSession, order_request_id: int
    ) -> list[DeliveryShipment]:
        statement = (
            select(DeliveryShipment)
            .join(DeliveryShipmentAllocation)
            .where(
                DeliveryShipment.kind == "international",
                DeliveryShipmentAllocation.order_request_id == order_request_id,
            )
            .options(*self.OPTIONS)
            .order_by(DeliveryShipment.date_added.asc())
        )

        return list((await db.execute(statement)).unique().scalars().all())

    async def allocated_by_item(
        self, db: AsyncSession, item_ids: Sequence[int]
    ) -> dict[int, int]:
        if not item_ids:
            return {}

        rows = (
            await db.execute(
                select(
                    DeliveryShipmentAllocation.order_request_item_id,
                    func.sum(DeliveryShipmentAllocation.quantity),
                )
                .where(DeliveryShipmentAllocation.order_request_item_id.in_(item_ids))
                .group_by(DeliveryShipmentAllocation.order_request_item_id)
            )
        ).all()

        return {item_id: int(quantity) for item_id, quantity in rows}


class DeliveryPreferenceDAO(DAO[DeliveryPreference, BaseModel, BaseModel]):
    async def get_for_order(
        self, db: AsyncSession, order_request_id: int
    ) -> DeliveryPreference | EmptyType:
        preference = await db.scalar(
            select(DeliveryPreference).where(
                DeliveryPreference.order_request_id == order_request_id
            )
        )

        return preference if preference is not None else Empty


class DeliveryFulfillmentDAO(DAO[DeliveryFulfillment, BaseModel, BaseModel]):
    OPTIONS: ClassVar[list] = [
        selectinload(DeliveryFulfillment.events),
        selectinload(DeliveryFulfillment.shipment).selectinload(
            DeliveryShipment.events
        ),
        selectinload(DeliveryFulfillment.shipment).selectinload(
            DeliveryShipment.allocations
        ),
    ]

    async def get_full(
        self, db: AsyncSession, fulfillment_id: int, *, for_update: bool = False
    ) -> DeliveryFulfillment | EmptyType:
        statement = (
            select(DeliveryFulfillment)
            .where(DeliveryFulfillment.id == fulfillment_id)
            .options(*self.OPTIONS)
        )

        if for_update:
            statement = statement.with_for_update(of=DeliveryFulfillment)

        value = (await db.execute(statement)).unique().scalar_one_or_none()

        return value if value is not None else Empty

    async def get_for_order(
        self, db: AsyncSession, order_request_id: int
    ) -> DeliveryFulfillment | EmptyType:
        statement = (
            select(DeliveryFulfillment)
            .where(DeliveryFulfillment.order_request_id == order_request_id)
            .options(*self.OPTIONS)
            .order_by(DeliveryFulfillment.date_added.desc())
            .limit(1)
        )

        value = (await db.execute(statement)).unique().scalar_one_or_none()

        return value if value is not None else Empty


dao_delivery_stages = DeliveryStageDAO(DeliveryStage)
dao_delivery_shipments = DeliveryShipmentDAO(DeliveryShipment)
dao_delivery_allocations = DAO(DeliveryShipmentAllocation)
dao_delivery_preferences = DeliveryPreferenceDAO(DeliveryPreference)
dao_delivery_fulfillments = DeliveryFulfillmentDAO(DeliveryFulfillment)
dao_delivery_events = DAO(DeliveryEvent)
