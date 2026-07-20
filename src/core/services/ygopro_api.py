from typing import TypedDict

from httpx import AsyncClient, HTTPStatusError, RequestError

from src.core.constants import YGO_API_URL


class YGOPROCardImage(TypedDict):
    id: int
    image_url: str
    image_url_small: str
    image_url_cropped: str


class YGOPROCard(TypedDict):
    id: int
    name: str
    type: str
    frameType: str
    card_images: list[dict]


class YGROPROResponse(TypedDict):
    data: list[YGOPROCard]
    error: str | None = None


async def fuzzy_search(query: str) -> list[YGROPROResponse]:
    normalized_query = query.strip().lower()

    if not normalized_query:
        return []

    async with AsyncClient(base_url=YGO_API_URL) as client:
        response = await client.get(params={"fname": normalized_query})

    payload = response.json()

    try:
        cache_value: list[YGROPROResponse]

        if isinstance(payload, list):
            cache_value = payload
        else:
            cache_value = [payload]
    except Exception:
        return payload

    return cache_value


async def get_card_by_id(id: int) -> YGROPROResponse:
    async with AsyncClient(base_url=YGO_API_URL) as client:
        response = await client.get(params={"id": id})

    return response.json()


async def safe_get_card_by_id(id: int) -> YGROPROResponse | None:
    try:
        return await get_card_by_id(id)
    except Exception:
        return None


async def get_cards_by_ids(ids: list[int]) -> list[YGOPROCard]:
    if not ids:
        return []

    joined_ids = ",".join(str(id) for id in ids)

    async with AsyncClient(base_url=YGO_API_URL) as client:
        try:
            response = await client.get(f"{YGO_API_URL}?id={joined_ids}")
            response.raise_for_status()
        except (HTTPStatusError, RequestError) as _:
            return []

    try:
        payload = response.json()
    except Exception:
        return []

    data = payload.get("data")

    if not isinstance(data, list):
        return []

    cards: list[YGOPROCard] = []

    for entry in data:
        if isinstance(entry, dict):
            cards.append(entry)

    return cards
