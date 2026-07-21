import pytest

from src.api.cards.application import card_cases
from src.api.cards.domain import CardNotFound
from src.core import Err
from src.core.services.cache import InMemoryCache
from src.core.utils.utils import Empty


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class MissingCardDAO:
    async def get(self, db: object, card_id: int) -> object:
        return Empty


@pytest.mark.anyio
async def test_get_card_returns_typed_error_when_card_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(card_cases, "dao", MissingCardDAO())

    result = await card_cases.get_one(object(), InMemoryCache(), 42)

    assert result == Err(CardNotFound(card_id=42))
