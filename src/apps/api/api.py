from litestar import Litestar, get

from src.apps.api.cards.presentation.http import cards_router
from src.apps.api.collections.presentation.http import collections_router
from src.apps.api.members.presentation.http import members_router
from src.apps.api.orders.presentation.http import orders_router


@get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = Litestar(route_handlers=[health, cards_router, collections_router, orders_router, members_router])
