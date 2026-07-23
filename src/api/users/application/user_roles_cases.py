from __future__ import annotations

from typing import TYPE_CHECKING, Any, Never, cast

from src.api.users.domain import UserRoleCreate, UserRoleNotFound, UserRoleUpdate
from src.api.roles.domain import SystemRoleIsImmutable
from src.api.users.repository import UserRole
from src.api.users.repository import dao_user_roles as dao
from src.core import Err, Ok, Result
from src.core.utils.filters import FilterTypes, OrderBy
from src.core.utils.utils import Empty

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_one(
    db: AsyncSession, user_role_id: int
) -> Result[UserRole, UserRoleNotFound]:
    user_role = await dao.get(db, user_role_id)

    if user_role is Empty:
        return Err(UserRoleNotFound(user_role_id))

    return Ok(user_role)


async def get_multi(
    db: AsyncSession,
    page: int = 1,
    shows: int | None = None,
    filters: dict[str, Any] | None = None,
    order_by: OrderBy | list[tuple[str, bool]] | None = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Result[tuple[list[UserRole], int], Never]:
    data, count = await dao.get_multi(
        db,
        page=(page - 1) * (shows or 20),
        shows=shows,
        where=filters,
        ordering=order_by or [("id", True)],
        complex_filters=complex_filters,
    )

    return Ok((data, count))


async def create(db: AsyncSession, obj_in: UserRoleCreate) -> Result[UserRole, Never]:
    user_role = await dao.create(db, obj_in=obj_in)

    return Ok(user_role)


async def update(
    db: AsyncSession,
    user_role_id: int,
    obj_in: UserRoleUpdate,
) -> Result[UserRole, UserRoleNotFound | SystemRoleIsImmutable]:
    user_role = await dao.get(db, user_role_id)

    if user_role is Empty:
        return Err(UserRoleNotFound(user_role_id))

    user_role = cast(UserRole, user_role)

    if user_role.role.is_system:
        return Err(SystemRoleIsImmutable(user_role.role_id))

    updated_user_role = await dao.update(db, user_role_id, obj_in)

    return Ok(updated_user_role)


async def remove(
    db: AsyncSession, user_role_id: int
) -> Result[None, UserRoleNotFound | SystemRoleIsImmutable]:
    user_role = await dao.get(db, user_role_id)

    if user_role is Empty:
        return Err(UserRoleNotFound(user_role_id))

    user_role = cast(UserRole, user_role)

    if user_role.role.is_system:
        return Err(SystemRoleIsImmutable(user_role.role_id))

    await dao.delete(db, db_object=user_role)

    return Ok(None)
