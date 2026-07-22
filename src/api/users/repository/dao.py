from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.api.users.domain import (
    UserAddressCreate,
    UserAddressUpdate,
    UserCreate,
    UserRoleCreate,
    UserRoleUpdate,
    UserUpdate,
)
from src.core.db import DAO
from src.core.utils.utils import Empty, EmptyType

from .models import User, UserAddress, UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserDAO(DAO[User, UserCreate, UserUpdate]):
    async def count_by_role_bridge(self, db: AsyncSession, role_bridge_id: int) -> int:
        count = await db.scalar(
            select(func.count()).select_from(User).where(User.role_id == role_bridge_id)
        )

        return count or 0


class UserAddressDAO(DAO[UserAddress, UserAddressCreate, UserAddressUpdate]):
    pass


class UserRoleDAO(DAO[UserRole, UserRoleCreate, UserRoleUpdate]):
    async def get_by_role_id(
        self, db: AsyncSession, role_id: int
    ) -> UserRole | EmptyType:
        bridge = await db.scalar(select(UserRole).where(UserRole.role_id == role_id))

        return bridge if bridge is not None else Empty

    async def get_system_role_bridge(
        self, db: AsyncSession, role_name: str
    ) -> UserRole | EmptyType:
        from src.api.roles.repository.models import Role

        bridge = await db.scalar(
            select(UserRole)
            .join(Role)
            .where(Role.name == role_name, Role.is_system.is_(True))
        )

        return bridge if bridge is not None else Empty

    async def ensure_for_role(self, db: AsyncSession, role_id: int) -> UserRole:
        bridge = await self.get_by_role_id(db, role_id)

        if bridge is Empty:
            bridge = UserRole(role_id=role_id)
            db.add(bridge)

            await db.flush()

        return bridge


dao_user_addresses = UserAddressDAO(UserAddress)
dao_users = UserDAO(User)
dao_user_roles = UserRoleDAO(UserRole)
