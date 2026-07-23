from __future__ import annotations

from typing import TYPE_CHECKING, Any, Never

from src.api.users.domain import (
    UserAddressCreate,
    UserAddressNotFound,
    UserAddressUpdate,
)
from src.api.users.repository import UserAddress
from src.api.users.repository import dao_user_addresses as dao
from src.core import Err, Ok, Result
from src.core.utils.filters import FilterTypes, OrderBy
from src.core.utils.utils import Empty

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_one(
    db: AsyncSession, user_address_id: int
) -> Result[UserAddress, UserAddressNotFound]:
    user_address = await dao.get(db, user_address_id)

    if user_address is Empty:
        return Err(UserAddressNotFound(user_address_id))

    return Ok(user_address)


async def get_multi(
    db: AsyncSession,
    page: int = 1,
    shows: int | None = None,
    filters: dict[str, Any] | None = None,
    order_by: OrderBy | list[tuple[str, bool]] | None = None,
    complex_filters: list[FilterTypes] | None = None,
) -> Result[tuple[list[UserAddress], int], Never]:
    data, count = await dao.get_multi(
        db,
        page=(page - 1) * (shows or 20),
        shows=shows,
        where=filters,
        ordering=order_by or [("id", True)],
        complex_filters=complex_filters,
    )

    return Ok((data, count))


async def create(
    db: AsyncSession, obj_in: UserAddressCreate
) -> Result[UserAddress, Never]:
    user_address = await dao.create(db, obj_in=obj_in)

    return Ok(user_address)


async def update(
    db: AsyncSession,
    user_address_id: int,
    obj_in: UserAddressUpdate,
) -> Result[UserAddress, UserAddressNotFound]:
    user_address = await dao.get(db, user_address_id)

    if user_address is Empty:
        return Err(UserAddressNotFound(user_address_id))

    updated_user_address = await dao.update(db, user_address_id, obj_in)

    return Ok(updated_user_address)


async def remove(
    db: AsyncSession, user_address_id: int
) -> Result[None, UserAddressNotFound]:
    user_address = await dao.get(db, user_address_id)

    if user_address is Empty:
        return Err(UserAddressNotFound(user_address_id))

    await dao.delete(db, db_object=user_address)

    return Ok(None)
