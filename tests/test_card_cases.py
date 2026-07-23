import pytest

from src.api.cards.application import card_cases
from src.api.cards.domain import CardListResponse, CardNotFound, CardResponse
from src.core import Err, Ok
from src.core.services.cache import InMemoryCache
from src.core.utils.utils import Empty


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class MissingCardDAO:
    async def get(self, db: object, card_id: int) -> object:
        return Empty


class PaginatedCardDAO:
    def __init__(self) -> None:
        self.reads = 0

    async def get_multi(self, db: object, **kwargs: object) -> tuple[list[object], int]:
        self.reads += 1
        return (
            [
                CardResponse(
                    id=1,
                    ygo_id=46986414,
                    sets={},
                    card_type="Normal Monster",
                    race="Spellcaster",
                    name="Dark Magician",
                    text="",
                    attribute="DARK",
                    prices={},
                    images={},
                    date_added="2026-07-23T12:00:00Z",
                )
            ],
            7,
        )


@pytest.mark.anyio
async def test_get_card_returns_typed_error_when_card_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(card_cases, "dao", MissingCardDAO())

    result = await card_cases.get_one(object(), InMemoryCache(), 42)

    assert result == Err(CardNotFound(card_id=42))


@pytest.mark.anyio
async def test_list_cards_caches_items_and_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dao = PaginatedCardDAO()
    cache = InMemoryCache()
    monkeypatch.setattr(card_cases, "dao", dao)

    first = await card_cases.get_multi(object(), cache, page=1, shows=10)
    second = await card_cases.get_multi(object(), cache, page=1, shows=10)

    assert isinstance(first, Ok)
    assert first.value == CardListResponse(items=first.value.items, total=7)
    assert second == first
    assert dao.reads == 1
