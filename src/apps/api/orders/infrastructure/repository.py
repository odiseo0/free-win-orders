from src.apps.api.orders.domain.entities import Order


class InMemoryOrderRepository:
    _orders: dict[str, Order] = {}

    async def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    async def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
