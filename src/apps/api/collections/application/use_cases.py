from src.apps.api.collections.application.dto import (
    AddCollectionItemCommand,
    CreateCollectionCommand,
    MarkCollectionItemRequestedCommand,
)
from src.apps.api.collections.domain.entities import Collection, CollectionItem
from src.apps.api.collections.domain.ports import CollectionRepository


class CreateCollectionUseCase:
    def __init__(self, repository: CollectionRepository) -> None:
        self.repository = repository

    async def execute(self, command: CreateCollectionCommand) -> Collection:
        collection = Collection(id=command.id, name=command.name)
        return await self.repository.save(collection)


class AddCollectionItemUseCase:
    def __init__(self, repository: CollectionRepository) -> None:
        self.repository = repository

    async def execute(self, command: AddCollectionItemCommand) -> Collection:
        item = CollectionItem(
            card_id=command.card_id,
            card_name=command.card_name,
            quantity=command.quantity,
        )
        return await self.repository.add_item(command.collection_id, item)


class MarkCollectionItemRequestedUseCase:
    def __init__(self, repository: CollectionRepository) -> None:
        self.repository = repository

    async def execute(self, command: MarkCollectionItemRequestedCommand) -> Collection | None:
        collection = await self.repository.get(command.collection_id)
        if collection is None:
            return None

        for item in collection.items:
            if item.card_id == command.card_id:
                item.status = "requested"
                break

        return await self.repository.save(collection)
