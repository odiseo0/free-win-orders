from __future__ import annotations

from typing import TYPE_CHECKING, Any

from result import Err, Ok

from src.api.users.domain import UserRoleCreate, UserRoleUpdate
from src.api.users.repository import UserRole
from src.api.users.repository import dao_user_roles as dao
from src.core.utils.filters import FilterTypes, OrderBy
from src.core.utils.utils import EmptyType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_one(db: AsyncSession, user_role_id: int) -> Ok[UserRole] | Err[EmptyType]:
    data = await dao.get(db, user_role_id)

    return Ok(data)


async def get_multi(
    db: AsyncSession,
    page: int = 1,
    shows: int | None = None,
    filters: dict[str, Any] | None = None,
    order_by: OrderBy | list[str, Any] = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Ok[tuple[list[UserRole], int]] | Err[list]:
    data, count = await dao.get_multi(
        db,
        page=(page - 1) * (shows or 20),
        shows=shows,
        where=filters,
        ordering=order_by or ["id", True],
        complex_filters=complex_filters,
    )

    if count is None:
        return Err([])

    return Ok((data, count))


async def create(db: AsyncSession, obj_in: UserRoleCreate) -> Ok[UserRole] | Err[None]:
    result = await dao.create(db, obj_in=obj_in)

    if result is None:
        return Err("No se pudo crear el usuario")

    return Ok(result)


async def update(
    db: AsyncSession,
    user_role_id: int,
    obj_in: UserRoleUpdate,
) -> Ok[UserRole] | Err[None]:
    result = await dao.update(db, user_role_id, obj_in)

    if result is None:
        return Err("Error")

    return Ok(result)


async def remove(db: AsyncSession, user_role_id: int) -> Ok[UserRole] | Err[None]:
    user_role = await dao.get(db, user_role_id)

    if user_role is EmptyType:
        return Err("Error")

    result = await dao.delete(db, db_object=user_role)

    return Ok(result)
