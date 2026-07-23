from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from src.core.schema import BaseModel


class Card(BaseModel):
    ygo_id: int | None = None
    sets: dict[str, Any] | None = None
    card_type: str | None = None
    race: str | None = None
    name: str | None = None
    text: str | None = None
    attribute: str | None = None
    prices: dict[str, Any] | None = None
    images: dict[str, Any] | None = None


class CardCreate(Card):
    ygo_id: int = Field(default=...)
    sets: dict[str, Any] = Field(default=...)
    card_type: str = Field(default=...)
    race: str = Field(default=...)
    name: str = Field(default=...)
    text: str = Field(default=...)
    attribute: str = Field(default=...)
    prices: dict[str, Any] = Field(default=...)
    images: dict[str, Any] = Field(default=...)


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
