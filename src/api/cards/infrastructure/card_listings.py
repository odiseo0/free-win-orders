from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.cards.application import card_listing_cases
from src.api.cards.domain import (
    CardListingNotFound,
    CardListingResponse,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.core.services.cache import Cache, get_cache
from src.core.services.scraper import CardListingSearch, get_card_listing_search

router = APIRouter(tags=["card-listings"])


@router.get("/search")
async def search_card_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    scraper: Annotated[CardListingSearch, Depends(get_card_listing_search)],
    query: Annotated[
        str,
        Query(min_length=1, max_length=255, pattern=r".*\S.*"),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[CardListingResponse]:
    result = await card_listing_cases.search(
        db,
        cache,
        scraper,
        query,
        limit=limit,
    )

    match result:
        case Ok(listings):
            return listings
        case Err(error):
            assert_never(error)


@router.get("/")
async def read_card_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[CardListingResponse]:
    result = await card_listing_cases.get_multi(
        db,
        cache,
        page=page,
        shows=shows,
    )

    match result:
        case Ok(listings):
            return listings
        case Err(error):
            assert_never(error)


@router.get("/{card_listing_id}")
async def read_card_listing(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Cache, Depends(get_cache)],
    card_listing_id: int,
) -> CardListingResponse:
    result = await card_listing_cases.get_one(db, cache, card_listing_id)

    match result:
        case Ok(listing):
            return listing
        case Err(CardListingNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La publicación de la carta no existe",
            )
        case unexpected:
            assert_never(unexpected)
