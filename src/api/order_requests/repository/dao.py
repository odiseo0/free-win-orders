from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.order_requests.domain import (
    OrderRequestEventType,
    OrderRequestStatus,
    quantize_usd,
)
from src.core.db.dao import catch_sqlalchemy_exception
from src.core.utils.utils import Empty, EmptyType, datetime_now

from .models import OrderRequest, OrderRequestHistory, OrderRequestItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CardListingSnapshot(Protocol):
    id: int
    name: str
    ygo_set: str
    code: str
    rarity: str
    condition: str
    price: Decimal


class OrderRequestDAO:
    async def get(
        self,
        db: AsyncSession,
        order_request_id: int,
    ) -> OrderRequest | EmptyType:
        statement = (
            select(OrderRequest)
            .where(OrderRequest.id == order_request_id)
            .options(selectinload(OrderRequest.items))
        )
        result = (await db.execute(statement)).unique().scalar_one_or_none()

        return result if result is not None else Empty

    async def get_for_update(
        self,
        db: AsyncSession,
        order_request_id: int,
    ) -> OrderRequest | EmptyType:
        statement = (
            select(OrderRequest)
            .where(OrderRequest.id == order_request_id)
            .options(selectinload(OrderRequest.items))
            .with_for_update()
        )
        result = (await db.execute(statement)).unique().scalar_one_or_none()

        return result if result is not None else Empty

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
        db.add(request)

        with catch_sqlalchemy_exception():
            await db.flush()

        return request

    async def flush(self, db: AsyncSession) -> None:
        with catch_sqlalchemy_exception():
            await db.flush()


class OrderRequestItemDAO:
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
        db.add(item)

        with catch_sqlalchemy_exception():
            await db.flush()

        return item

class OrderRequestHistoryDAO:
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
        db.add(history)

        with catch_sqlalchemy_exception():
            await db.flush()

        return history


dao_order_requests = OrderRequestDAO()
dao_order_request_items = OrderRequestItemDAO()
dao_order_request_histories = OrderRequestHistoryDAO()
