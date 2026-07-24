from __future__ import annotations

from typing import TYPE_CHECKING, Any, Never, cast

from src.api.roles.domain import RoleNotFound
from src.api.users.domain import UserCreate, UserNotFound, UserUpdate
from src.api.users.repository import User
from src.api.users.repository import dao_user_roles as role_dao
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
    order_by: OrderBy | list[tuple[str, bool]] | None = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Result[tuple[list[User], int], Never]:
    data, count = await dao.get_multi(
        db,
        page=(page - 1) * (shows or 20),
        shows=shows,
        where=filters,
        ordering=order_by or [("id", True)],
        complex_filters=complex_filters,
    )

    return Ok((data, count))


async def create(db: AsyncSession, obj_in: UserCreate) -> Result[User, Never]:
    bridge = await role_dao.get_system_role_bridge(db, "User")

    if bridge is Empty:
        raise RuntimeError("El rol de sistema User no está inicializado")

    data = obj_in.model_dump(mode="python")
    data["role_id"] = bridge.id
    user = await dao.create(db, obj_in=data)

    return Ok(user)


async def assign_role(
    db: AsyncSession, user_id: int, role_id: int
) -> Result[User, UserNotFound | RoleNotFound]:
    user = await dao.get(db, user_id)

    if user is Empty:
        return Err(UserNotFound(user_id))

    bridge = await role_dao.get_by_role_id(db, role_id)

    if bridge is Empty:
        return Err(RoleNotFound(role_id))

    updated_user = await dao.update(db, user_id, {"role_id": bridge.id})

    return Ok(updated_user)


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
