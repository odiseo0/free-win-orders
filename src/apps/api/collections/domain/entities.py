from dataclasses import dataclass, field


@dataclass(slots=True)
class CollectionItem:
    card_id: str
    card_name: str
    quantity: int
    status: str = "draft"


@dataclass(slots=True)
class Collection:
    id: str
    name: str
    items: list[CollectionItem] = field(default_factory=list)
