from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.core.schema import BaseModel


class Card(BaseModel):
    ygo_id: int | None = None
    sets: dict[str, object] | None = None
    card_type: str | None = None
    race: str | None = None
    name: str | None = None
    text: str | None = None
    attribute: str | None = None
    prices: dict[str, object] | None = None
    images: dict[str, object] | None = None


class CardCreate(Card):
    ygo_id: int
    sets: dict[str, object]
    card_type: str
    race: str
    name: str
    text: str
    attribute: str
    prices: dict[str, object]
    images: dict[str, object]


class CardUpdate(Card):
    pass


class CardResponse(CardCreate):
    id: int
    date_added: datetime
    date_updated: datetime | None = None


class CardListingResponse(BaseModel):
    id: int | None = None
    card_id: int | None = None
    ygo_id: int | None = None
    ygo_set: str
    name: str
    code: str
    price: Decimal
    rarity: str
    condition: str
    stock: int = 0
    date_added: datetime | None = None
    date_updated: datetime | None = None
