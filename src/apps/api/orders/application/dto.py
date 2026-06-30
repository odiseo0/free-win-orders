from dataclasses import dataclass


@dataclass(slots=True)
class CreateOrderCommand:
    id: str
    collection_id: str
