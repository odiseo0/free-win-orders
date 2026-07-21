from __future__ import annotations

from typing import TYPE_CHECKING, Any, Never

from src.api.users.domain import UserCreate, UserNotFound, UserUpdate
from src.api.users.repository import User
from src.api.users.repository import dao_users as dao
from src.core import Err, Ok, Result
from src.core.utils.filters import FilterTypes, OrderBy
from src.core.utils.utils import Empty

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_one(db: AsyncSession, user_id: int) -> Result[User, UserNotFound]:
    user = await dao.get(db, user_id)

    if user is Empty:
        return Err(UserNotFound(user_id))

    return Ok(user)


async def get_multi(
    db: AsyncSession,
    page: int = 1,
    shows: int | None = None,
    filters: dict[str, Any] | None = None,
    order_by: OrderBy | list[str, Any] = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Result[tuple[list[User], int], Never]:
    data, count = await dao.get_multi(
        db,
        page=(page - 1) * (shows or 20),
        shows=shows,
        where=filters,
        ordering=order_by or ["id", True],
        complex_filters=complex_filters,
    )

    return Ok((data, count))


async def create(db: AsyncSession, obj_in: UserCreate) -> Result[User, Never]:
    user = await dao.create(db, obj_in=obj_in)

    return Ok(user)


async def update(
    db: AsyncSession,
    user_id: int,
    obj_in: UserUpdate,
) -> Result[User, UserNotFound]:
    user = await dao.get(db, user_id)

    if user is Empty:
        return Err(UserNotFound(user_id))

    updated_user = await dao.update(db, user_id, obj_in)

    return Ok(updated_user)


async def remove(db: AsyncSession, user_id: int) -> Result[None, UserNotFound]:
    user = await dao.get(db, user_id)

    if user is Empty:
        return Err(UserNotFound(user_id))

    await dao.delete(db, db_object=user)

    return Ok(None)
