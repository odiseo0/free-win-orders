from fastapi import APIRouter

from src.api.order_periods import order_periods_router
from src.api.order_requests import order_requests_router
from src.api.roles import permissions_router, roles_router
from src.api.users import user_addresses_router, user_roles_router, users_router

router = APIRouter()
router.include_router(users_router, prefix="/users")
router.include_router(user_addresses_router, prefix="/user-addresses")
router.include_router(user_roles_router, prefix="/user-roles")
router.include_router(roles_router, prefix="/roles")
router.include_router(permissions_router, prefix="/permissions")
router.include_router(order_periods_router, prefix="/order-periods")
router.include_router(order_requests_router, prefix="/order-requests")
