from src.apps.api.collections.domain.entities import Collection, CollectionItem


class InMemoryCollectionRepository:
    _collections: dict[str, Collection] = {}

    async def get(self, collection_id: str) -> Collection | None:
        return self._collections.get(collection_id)

    async def save(self, collection: Collection) -> Collection:
        self._collections[collection.id] = collection
        return collection

    async def add_item(self, collection_id: str, item: CollectionItem) -> Collection:
        collection = self._collections[collection_id]
        collection.items.append(item)
        self._collections[collection_id] = collection
        return collection
