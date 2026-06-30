from uuid import uuid4

from litestar import Controller, Router, get, post

from src.apps.api.orders.application.dto import CreateOrderCommand
from src.apps.api.orders.application.use_cases import CreateOrderUseCase
from src.apps.api.orders.infrastructure.repository import InMemoryOrderRepository

repository = InMemoryOrderRepository()


def _serialize_order(order: object) -> dict:
    return {
        "id": order.id,
        "collection_id": order.collection_id,
        "status": order.status,
        "items": [
            {"card_id": item.card_id, "card_name": item.card_name, "quantity": item.quantity}
            for item in order.items
        ],
    }


class OrdersController(Controller):
    path = "/orders"

    @post()
    async def create(self, collection_id: str) -> dict:
        use_case = CreateOrderUseCase(repository=repository)
        order = await use_case.execute(CreateOrderCommand(id=str(uuid4()), collection_id=collection_id))
        return _serialize_order(order)

    @get("/{order_id:str}")
    async def get_order(self, order_id: str) -> dict | None:
        order = await repository.get(order_id)
        return None if order is None else _serialize_order(order)


orders_router = Router(path="", route_handlers=[OrdersController])
