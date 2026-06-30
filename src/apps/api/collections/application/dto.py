from dataclasses import dataclass


@dataclass(slots=True)
class CreateCollectionCommand:
    id: str
    name: str


@dataclass(slots=True)
class AddCollectionItemCommand:
    collection_id: str
    card_id: str
    card_name: str
    quantity: int


@dataclass(slots=True)
class MarkCollectionItemRequestedCommand:
    collection_id: str
    card_id: str
