from src.apps.api.orders.application.dto import CreateOrderCommand
from src.apps.api.orders.domain.entities import Order
from src.apps.api.orders.domain.ports import OrderRepository


class CreateOrderUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    async def execute(self, command: CreateOrderCommand) -> Order:
        order = Order(id=command.id, collection_id=command.collection_id)
        return await self.repository.save(order)
