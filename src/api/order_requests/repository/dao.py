from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.order_requests.domain import (
    OrderRequestEventType,
    OrderRequestStatus,
    quantize_usd,
)
from src.core.db import DAO
from src.core.utils.utils import Empty, EmptyType, datetime_now

from .models import OrderRequest, OrderRequestHistory, OrderRequestItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .card_listings import CardListingSnapshot


class OrderRequestDAO(DAO[OrderRequest, BaseModel, BaseModel]):
    def __init__(self) -> None:
        super().__init__(
            OrderRequest,
            default_options=[("items", "selectinload")],
        )

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        page: int,
        shows: int,
        owner_user_id: int | None = None,
        order_period_id: int | None = None,
        status: OrderRequestStatus | None = None,
    ) -> tuple[list[OrderRequest], int]:
        conditions = []

        if owner_user_id is not None:
            conditions.append(OrderRequest.created_by_user_id == owner_user_id)

        if order_period_id is not None:
            conditions.append(OrderRequest.order_period_id == order_period_id)

        if status is not None:
            conditions.append(OrderRequest.status == status)

        filtered = select(OrderRequest).where(*conditions)
        count_statement = filtered.with_only_columns(
            func.count(),
            maintain_column_froms=True,
        ).order_by(None)
        total = (await db.execute(count_statement)).scalar_one()
        data_statement = (
            filtered.options(selectinload(OrderRequest.items))
            .order_by(OrderRequest.date_added.desc())
            .offset(page)
            .limit(shows)
        )
        requests = (await db.execute(data_statement)).unique().scalars().all()

        return list(requests), total

    async def create(
        self,
        db: AsyncSession,
        *,
        order_period_id: int,
        created_by_user_id: int,
        note: str | None,
    ) -> OrderRequest:
        request = OrderRequest(
            order_period_id=order_period_id,
            created_by_user_id=created_by_user_id,
            note=note,
        )

        return await self.add(db, request)


class OrderRequestItemDAO(DAO[OrderRequestItem, BaseModel, BaseModel]):
    def __init__(self) -> None:
        super().__init__(OrderRequestItem)

    async def get_for_request(
        self,
        db: AsyncSession,
        *,
        order_request_id: int,
        item_id: int,
    ) -> OrderRequestItem | EmptyType:
        statement = select(OrderRequestItem).where(
            OrderRequestItem.id == item_id,
            OrderRequestItem.order_request_id == order_request_id,
        )
        result = (await db.execute(statement)).scalar_one_or_none()

        return result if result is not None else Empty

    async def get_active_for_request(
        self,
        db: AsyncSession,
        order_request_id: int,
    ) -> list[OrderRequestItem]:
        statement = (
            select(OrderRequestItem)
            .where(
                OrderRequestItem.order_request_id == order_request_id,
                OrderRequestItem.removed_at.is_(None),
            )
            .order_by(OrderRequestItem.date_added.asc())
        )

        return list((await db.execute(statement)).scalars().all())

    async def create_from_listing(
        self,
        db: AsyncSession,
        *,
        order_request_id: int,
        listing: CardListingSnapshot,
        requested_quantity: int,
    ) -> OrderRequestItem:
        item = OrderRequestItem(
            order_request_id=order_request_id,
            card_listing_id=listing.id,
            card_name=listing.name,
            card_set=listing.ygo_set,
            card_code=listing.code,
            rarity=listing.rarity,
            condition=listing.condition,
            estimated_unit_price=quantize_usd(listing.price),
            requested_quantity=requested_quantity,
            agreed_quantity=requested_quantity,
        )

        return await self.add(db, item)


class OrderRequestHistoryDAO(DAO[OrderRequestHistory, BaseModel, BaseModel]):
    def __init__(self) -> None:
        super().__init__(OrderRequestHistory)

    async def get_for_request(
        self,
        db: AsyncSession,
        *,
        order_request_id: int,
        page: int,
        shows: int,
    ) -> list[OrderRequestHistory]:
        statement = (
            select(OrderRequestHistory)
            .where(OrderRequestHistory.order_request_id == order_request_id)
            .order_by(OrderRequestHistory.occurred_at.desc())
            .offset(page)
            .limit(shows)
        )

        return list((await db.execute(statement)).scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        order_request_id: int,
        event: OrderRequestEventType,
        actor_user_id: int,
        changes: list[dict[str, object]],
        occurred_at: datetime | None = None,
    ) -> OrderRequestHistory:
        history = OrderRequestHistory(
            order_request_id=order_request_id,
            event=event,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at or datetime_now(),
            changes=changes,
        )

        return await self.add(db, history)


dao_order_requests = OrderRequestDAO()
dao_order_request_items = OrderRequestItemDAO()
dao_order_request_histories = OrderRequestHistoryDAO()
