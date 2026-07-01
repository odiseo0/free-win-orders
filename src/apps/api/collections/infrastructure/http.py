from uuid import uuid4

from litestar import Controller, Router, get, patch, post

from src.apps.api.collections.application.dto import (
    AddCollectionItemCommand,
    CreateCollectionCommand,
    MarkCollectionItemRequestedCommand,
)
from src.apps.api.collections.application.use_cases import (
    AddCollectionItemUseCase,
    CreateCollectionUseCase,
    MarkCollectionItemRequestedUseCase,
)
from src.apps.api.collections.infrastructure.repository import InMemoryCollectionRepository

repository = InMemoryCollectionRepository()


def _serialize_collection(collection: object) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "items": [
            {
                "card_id": item.card_id,
                "card_name": item.card_name,
                "quantity": item.quantity,
                "status": item.status,
            }
            for item in collection.items
        ],
    }


class CollectionsController(Controller):
    path = "/collections"

    @post()
    async def create(self, name: str) -> dict:
        use_case = CreateCollectionUseCase(repository=repository)
        collection = await use_case.execute(CreateCollectionCommand(id=str(uuid4()), name=name))
        return _serialize_collection(collection)

    @get("/{collection_id:str}")
    async def get_collection(self, collection_id: str) -> dict | None:
        collection = await repository.get(collection_id)
        return None if collection is None else _serialize_collection(collection)

    @post("/{collection_id:str}/items")
    async def add_item(self, collection_id: str, card_id: str, card_name: str, quantity: int = 1) -> dict:
        use_case = AddCollectionItemUseCase(repository=repository)
        collection = await use_case.execute(
            AddCollectionItemCommand(
                collection_id=collection_id,
                card_id=card_id,
                card_name=card_name,
                quantity=quantity,
            )
        )
        return _serialize_collection(collection)

    @patch("/{collection_id:str}/items/{card_id:str}/requested")
    async def mark_requested(self, collection_id: str, card_id: str) -> dict | None:
        use_case = MarkCollectionItemRequestedUseCase(repository=repository)
        collection = await use_case.execute(
            MarkCollectionItemRequestedCommand(collection_id=collection_id, card_id=card_id)
        )
        return None if collection is None else _serialize_collection(collection)


collections_router = Router(path="", route_handlers=[CollectionsController])
