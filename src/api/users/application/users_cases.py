from __future__ import annotations

from typing import TYPE_CHECKING, Any

from result import Err, Ok

from src.api.users.domain import UserCreate, UserUpdate
from src.api.users.repository import User
from src.api.users.repository import dao_users as dao
from src.core.utils.filters import FilterTypes, OrderBy
from src.core.utils.utils import EmptyType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_one(db: AsyncSession, user_id: int) -> Ok[User] | Err[EmptyType]:
    data = await dao.get(db, user_id)

    return Ok(data)


async def get_multi(
    db: AsyncSession,
    page: int = 1,
    shows: int | None = None,
    filters: dict[str, Any] | None = None,
    order_by: OrderBy | list[str, Any] = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Ok[tuple[list[User], int]] | Err[list]:
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


async def create(db: AsyncSession, obj_in: UserCreate) -> Ok[User] | Err[None]:
    result = await dao.create(db, obj_in=obj_in)

    if result is None:
        return Err("No se pudo crear el usuario")

    return Ok(result)


async def update(
    db: AsyncSession,
    user_id: int,
    obj_in: UserUpdate,
) -> Ok[User] | Err[None]:
    result = await dao.update(db, user_id, obj_in)

    if result is None:
        return Err("Error")

    return Ok(result)


async def remove(db: AsyncSession, user_id: int) -> Ok[User] | Err[None]:
    user = await dao.get(db, user_id)

    if user is EmptyType:
        return Err("Error")

    result = await dao.delete(db, db_object=user)

    return Ok(result)
