import time
from collections.abc import Mapping, Sequence
from typing import TypedDict
from urllib.parse import quote_plus

from httpx import AsyncClient, HTTPStatusError, RequestError

from src.utils.constants import YGO_API_URL
from src.utils.file_cache import load_cache_entry, save_cache_entry


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


_YGOPRO_CLIENT: AsyncClient | None = None
YGOPRO_FUZZY_TTL_SECONDS = 900
_YGOPRO_FUZZY_CACHE: dict[str, tuple[float, list[YGROPROResponse]]] = {}
USE_YGOPRO_FILE_CACHE = False


async def get_ygopro_client() -> AsyncClient:
    global _YGOPRO_CLIENT

    if _YGOPRO_CLIENT is None:
        _YGOPRO_CLIENT = AsyncClient()

    return _YGOPRO_CLIENT


async def close_ygopro_client() -> None:
    global _YGOPRO_CLIENT

    if _YGOPRO_CLIENT is not None:
        await _YGOPRO_CLIENT.aclose()
        _YGOPRO_CLIENT = None


async def fuzzy_search(query: str) -> list[YGROPROResponse]:
    normalized_query = query.strip().lower()

    if not normalized_query:
        return []

    now = time.monotonic()
    cached = _YGOPRO_FUZZY_CACHE.get(normalized_query)

    if cached is not None:
        expires_at, cached_payload = cached

        if expires_at > now:
            return cached_payload

    if USE_YGOPRO_FILE_CACHE:
        file_payload = load_cache_entry("ygopro_fuzzy", normalized_query)

        if file_payload is not None:
            try:
                cache_value = file_payload
                _YGOPRO_FUZZY_CACHE[normalized_query] = (
                    now + YGOPRO_FUZZY_TTL_SECONDS,
                    cache_value,
                )

                return cache_value
            except Exception:
                pass

    client = await get_ygopro_client()
    response = await client.get(f"{YGO_API_URL}?fname={normalized_query}")
    payload = response.json()

    try:
        cache_value: list[YGROPROResponse]

        if isinstance(payload, list):
            cache_value = payload
        else:
            cache_value = [payload]

        _YGOPRO_FUZZY_CACHE[normalized_query] = (
            now + YGOPRO_FUZZY_TTL_SECONDS,
            cache_value,
        )

        if USE_YGOPRO_FILE_CACHE:
            save_cache_entry("ygopro_fuzzy", normalized_query, cache_value)
    except Exception:
        return payload

    return cache_value


async def get_card_by_id(id: int) -> YGROPROResponse:
    client = await get_ygopro_client()
    response = await client.get(f"{YGO_API_URL}?id={id}")

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

    client = await get_ygopro_client()

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


async def get_card_image_url_by_name(name: str) -> str | None:
    query = name.strip()

    if not query:
        return None

    encoded_name = quote_plus(query)

    client = await get_ygopro_client()

    try:
        response = await client.get(f"{YGO_API_URL}?name={encoded_name}")
        response.raise_for_status()
    except (HTTPStatusError, RequestError):
        return None

    try:
        payload = response.json()
    except Exception:
        return None

    if not isinstance(payload, Mapping):
        return None

    data = payload.get("data")

    if not isinstance(data, Sequence) or not data:
        return None

    first_entry = data[0]

    if not isinstance(first_entry, Mapping):
        return None

    card_images = first_entry.get("card_images")

    if not isinstance(card_images, Sequence) or not card_images:
        return None

    first_image = card_images[1]

    if not isinstance(first_image, Mapping):
        return None

    image_url = first_image.get("image_url")

    if not isinstance(image_url, str):
        return None

    cleaned_url = image_url.strip()

    if not cleaned_url:
        return None

    return cleaned_url
