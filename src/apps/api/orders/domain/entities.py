from dataclasses import dataclass, field


@dataclass(slots=True)
class OrderItem:
    card_id: str
    card_name: str
    quantity: int


@dataclass(slots=True)
class Order:
    id: str
    collection_id: str
    status: str = "draft"
    items: list[OrderItem] = field(default_factory=list)
