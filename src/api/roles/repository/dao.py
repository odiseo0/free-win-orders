from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from src.api.roles.domain import (
    PermissionCode,
    PermissionCreate,
    PermissionUpdate,
    RoleCreate,
    RoleUpdate,
)
from src.core.db import DAO
from src.core.utils.utils import Empty, EmptyType

from .models import Permission, Role, RolePermission

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ActorRecord:
    user_id: int
    permission_codes: frozenset[str]


class RoleDAO(DAO[Role, RoleCreate, RoleUpdate]):
    async def upsert_system(
        self, db: AsyncSession, *, name: str, description: str
    ) -> Role:
        role = await db.scalar(select(self.model).where(self.model.name == name))

        if role is None:
            role = self.model(
                name=name,
                description=description,
                is_system=True,
            )
            db.add(role)
            await db.flush()
        else:
            role.description = description
            role.is_system = True

        return role


class PermissionDAO(DAO[Permission, PermissionCreate, PermissionUpdate]):
    async def get_by_codes(self, db: AsyncSession, codes: set[str]) -> list[Permission]:
        if not codes:
            return []

        permissions = (
            (await db.execute(select(self.model).where(self.model.code.in_(codes))))
            .scalars()
            .all()
        )

        return list(permissions)

    async def upsert(
        self, db: AsyncSession, *, code: PermissionCode, description: str
    ) -> Permission:
        permission = await db.scalar(
            select(self.model).where(self.model.code == code.value)
        )

        if permission is None:
            permission = self.model(code=code.value, description=description)
            db.add(permission)
            await db.flush()
        else:
            permission.description = description

        return permission


class RolePermissionDAO:
    async def replace(
        self,
        db: AsyncSession,
        *,
        role_id: int,
        permissions: list[Permission],
        commit: bool = True,
    ) -> None:
        await db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )

        db.add_all(
            RolePermission(role_id=role_id, permission_id=permission.id)
            for permission in permissions
        )

        if commit:
            await db.commit()


class AuthorizationDAO:
    async def get_actor(
        self, db: AsyncSession, user_id: int
    ) -> ActorRecord | EmptyType:
        from src.api.users.repository.models import User, UserRole

        rows = (
            await db.execute(
                select(User.id, Permission.code)
                .join(UserRole, User.role_id == UserRole.id)
                .join(Role, UserRole.role_id == Role.id)
                .outerjoin(RolePermission, RolePermission.role_id == Role.id)
                .outerjoin(Permission, Permission.id == RolePermission.permission_id)
                .where(User.id == user_id)
            )
        ).all()

        if not rows:
            return Empty

        return ActorRecord(
            user_id=rows[0][0],
            permission_codes=frozenset(code for _, code in rows if code is not None),
        )


dao_authorization = AuthorizationDAO()
dao_permissions = PermissionDAO(Permission)
dao_role_permissions = RolePermissionDAO()
dao_roles = RoleDAO(Role)
