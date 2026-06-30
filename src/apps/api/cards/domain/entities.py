from dataclasses import dataclass


@dataclass(slots=True)
class Card:
    id: str
    name: str
    quantity: int = 1
