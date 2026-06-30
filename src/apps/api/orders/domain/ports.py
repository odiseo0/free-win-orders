from typing import Protocol

from src.apps.api.orders.domain.entities import Order


class OrderRepository(Protocol):
    async def save(self, order: Order) -> Order: ...
    async def get(self, order_id: str) -> Order | None: ...
