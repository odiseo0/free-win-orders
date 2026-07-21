from fastapi import APIRouter

from src.api.cards import card_listings_router, cards_router
from src.api.users import user_addresses_router, user_roles_router, users_router

router = APIRouter()
router.include_router(cards_router, prefix="/cards")
router.include_router(card_listings_router, prefix="/card-listings")
router.include_router(users_router, prefix="/users")
router.include_router(user_addresses_router, prefix="/user-addresses")
router.include_router(user_roles_router, prefix="/user-roles")
