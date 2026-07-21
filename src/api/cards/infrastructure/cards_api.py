from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.cards.application import card_cases
from src.api.cards.domain import (
    CardCreate,
    CardNotFound,
    CardResponse,
    CardUpdate,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.core.services.cache import Cache, get_cache

router = APIRouter(tags=["cards"])


@router.get("/")
async def read_cards(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[CardResponse]:
    result = await card_cases.get_multi(db, cache, page=page, shows=shows)

    match result:
        case Ok(cards):
            return cards
        case Err(error):
            assert_never(error)


@router.get("/{card_id}")
async def read_card(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    card_id: int,
) -> CardResponse:
    result = await card_cases.get_one(db, cache, card_id)

    match result:
        case Ok(card):
            return card
        case Err(CardNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La carta no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_card(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    card_in: CardCreate,
) -> CardResponse:
    result = await card_cases.create(db, cache, card_in)

    match result:
        case Ok(card):
            return card
        case Err(error):
            assert_never(error)


@router.patch("/{card_id}")
async def update_card(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    card_id: int,
    card_in: CardUpdate,
) -> CardResponse:
    result = await card_cases.update(db, cache, card_id, card_in)

    match result:
        case Ok(card):
            return card
        case Err(CardNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La carta no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    card_id: int,
) -> Response:
    result = await card_cases.remove(db, cache, card_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Err(CardNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La carta no existe",
            )
        case unexpected:
            assert_never(unexpected)
