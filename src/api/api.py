from fastapi import APIRouter

from src.api.users import user_addresses_router, user_roles_router, users_router

router = APIRouter()
router.include_router(users_router, prefix="/users")
router.include_router(user_addresses_router, prefix="/user-addresses")
router.include_router(user_roles_router, prefix="/user-roles")
