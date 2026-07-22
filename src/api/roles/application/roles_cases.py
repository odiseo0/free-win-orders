from __future__ import annotations

from typing import TYPE_CHECKING, Never

from src.api.roles.domain import (
    PermissionCode,
    RoleCreate,
    RoleIsAssigned,
    RoleNameAlreadyExists,
    RoleNotFound,
    RoleUpdate,
    SystemRoleIsImmutable,
)
from src.api.roles.repository import (
    Permission,
    Role,
    dao_permissions,
    dao_role_permissions,
    dao_roles,
)
from src.api.users.repository import dao_user_roles, dao_users
from src.core import Err, Ok, Result
from src.core.db import DAOIntegrityError, StrategyOptions
from src.core.utils.utils import Empty

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


ROLE_RELATION_OPTIONS: list[tuple[str, StrategyOptions]] = [
    ("permissions", "selectinload")
]


async def get_multi(db: AsyncSession) -> Result[list[Role], Never]:
    roles, _ = await dao_roles.get_multi(
        db,
        shows=None,
        ordering=[("id", False)],
        options=ROLE_RELATION_OPTIONS,
    )

    return Ok(roles)


async def get_one(db: AsyncSession, role_id: int) -> Result[Role, RoleNotFound]:
    role = await dao_roles.get(db, role_id, options=ROLE_RELATION_OPTIONS)

    if role is Empty:
        return Err(RoleNotFound(role_id))

    return Ok(role)


async def get_permissions(db: AsyncSession) -> Result[list[Permission], Never]:
    permissions, _ = await dao_permissions.get_multi(
        db,
        shows=None,
        ordering=[("code", False)],
    )

    return Ok(permissions)


async def create(
    db: AsyncSession, role_in: RoleCreate
) -> Result[Role, RoleNameAlreadyExists]:
    existing = await dao_roles.get_by(db, {"name": role_in.name})

    if existing is not Empty:
        return Err(RoleNameAlreadyExists(role_in.name))

    try:
        role = await dao_roles.create(
            db,
            obj_in=role_in,
            commit=False,
            options=ROLE_RELATION_OPTIONS,
        )
        await dao_user_roles.ensure_for_role(db, role.id)
        await db.commit()
    except DAOIntegrityError:
        await db.rollback()
        return Err(RoleNameAlreadyExists(role_in.name))

    created_role = await dao_roles.get(db, role.id, options=ROLE_RELATION_OPTIONS)

    if created_role is Empty:
        raise RuntimeError("El rol desapareció después de crearlo")

    return Ok(created_role)


async def update(
    db: AsyncSession, role_id: int, role_in: RoleUpdate
) -> Result[Role, RoleNotFound | RoleNameAlreadyExists | SystemRoleIsImmutable]:
    role = await dao_roles.get(db, role_id, options=ROLE_RELATION_OPTIONS)

    if role is Empty:
        return Err(RoleNotFound(role_id))
    if role.is_system:
        return Err(SystemRoleIsImmutable(role_id))

    try:
        updated_role = await dao_roles.update(
            db,
            role_id,
            role_in,
            options=ROLE_RELATION_OPTIONS,
        )
    except DAOIntegrityError:
        await db.rollback()
        return Err(RoleNameAlreadyExists(role_in.name or role.name))

    return Ok(updated_role)


async def remove(
    db: AsyncSession, role_id: int
) -> Result[None, RoleNotFound | RoleIsAssigned | SystemRoleIsImmutable]:
    role = await dao_roles.get(db, role_id, options=ROLE_RELATION_OPTIONS)

    if role is Empty:
        return Err(RoleNotFound(role_id))
    if role.is_system:
        return Err(SystemRoleIsImmutable(role_id))

    bridge = await dao_user_roles.get_by_role_id(db, role_id)

    if bridge is not Empty:
        assignments = await dao_users.count_by_role_bridge(db, bridge.id)

        if assignments:
            return Err(RoleIsAssigned(role_id))

        await dao_user_roles.delete(db, bridge, commit=False)

    await dao_roles.delete(db, role)

    return Ok(None)


async def replace_permissions(
    db: AsyncSession, role_id: int, codes: list[PermissionCode]
) -> Result[Role, RoleNotFound | SystemRoleIsImmutable]:
    role = await dao_roles.get(db, role_id, options=ROLE_RELATION_OPTIONS)

    if role is Empty:
        return Err(RoleNotFound(role_id))
    if role.is_system:
        return Err(SystemRoleIsImmutable(role_id))

    unique_codes = {code.value for code in codes}
    permissions = await dao_permissions.get_by_codes(db, unique_codes)

    if len(permissions) != len(unique_codes):
        raise RuntimeError("El catálogo de permisos no está inicializado")

    await dao_role_permissions.replace(db, role_id=role_id, permissions=permissions)
    updated_role = await dao_roles.get(db, role_id, options=ROLE_RELATION_OPTIONS)

    if updated_role is Empty:
        raise RuntimeError("El rol desapareció después de actualizar sus permisos")

    return Ok(updated_role)
