from src.api.users.domain import (
    UserAddressCreate,
    UserAddressUpdate,
    UserCreate,
    UserRoleCreate,
    UserRoleUpdate,
    UserUpdate,
)
from src.core.db import DAO

from .models import User, UserAddress, UserRole


class UserDAO(DAO[User, UserCreate, UserUpdate]):
    pass


class UserAddressDAO(DAO[UserAddress, UserAddressCreate, UserAddressUpdate]):
    pass


class UserRoleDAO(DAO[UserRole, UserRoleCreate, UserRoleUpdate]):
    pass


dao_user_addresses = UserAddressDAO(UserAddress)
dao_users = UserDAO(User)
dao_user_roles = UserRoleDAO(UserRole)
