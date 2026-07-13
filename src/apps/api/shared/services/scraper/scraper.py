import asyncio
from urllib.parse import quote

from httpx import AsyncClient, HTTPStatusError, RequestError

from src.apps.api.shared.constants import BASE_URL, REQUEST_TIMEOUT_SECONDS, USER_AGENT

MAX_SCRAPE_CONCURRENCY = 50
PARSE_MAX_WORKERS = 32
CARD_LISTINGS_TTL_SECONDS = 600

_SCRAPER_CLIENT: AsyncClient | None = None


async def get_scraper_client() -> AsyncClient:
    global _SCRAPER_CLIENT

    if _SCRAPER_CLIENT is None:
        _SCRAPER_CLIENT = AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    return _SCRAPER_CLIENT


async def scrape_cards(cards: list[str]) -> list:
    client = await get_scraper_client()
    semaphore = asyncio.Semaphore(MAX_SCRAPE_CONCURRENCY)
    tasks: list[asyncio.Task] = []
    card_names: list[str] = []

    async def _bounded_fetch(url: str) -> str | None:
        async with semaphore:
            return await fetch_card_page(client, url)

    for card_name in cards:
        encoded_name = quote(card_name, safe="").replace("%20", "+")
        url = f"{BASE_URL}{encoded_name}"
        task = asyncio.create_task(_bounded_fetch(url))
        tasks.append(task)
        card_names.append(card_name)

    htmls = await asyncio.gather(*tasks)

    return htmls


async def fetch_card_page(client: AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
    except HTTPStatusError as error:
        if error.response.status_code == 404:
            return None

        return None
    except RequestError:
        return None
