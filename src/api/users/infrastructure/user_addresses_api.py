from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.user_address_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import (
    UserAddressCreate,
    UserAddressResponse,
    UserAddressUpdate,
)
from src.core.db import get_db

router = APIRouter(tags=["user-addresses"])


@router.get("/")
async def read_user_addresses(
    db: Annotated[AsyncSession, Depends(get_db)], page: int = 0, shows: int = 100
) -> list[UserAddressResponse]:
    return await get_multi(db, page=page, shows=shows)


@router.get("/{user_address_id}")
async def read_user_address(
    db: Annotated[AsyncSession, Depends(get_db)], user_address_id: int
) -> UserAddressResponse:
    return await get_one(db, user_address_id)


@router.post("/")
async def create_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_address_in: UserAddressCreate,
) -> UserAddressResponse:
    return await create(db, obj_in=user_address_in)


@router.patch("/{user_address_id}")
async def update_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_address_id: int,
    user_address_in: UserAddressUpdate,
) -> UserAddressResponse:
    return await update(
        db,
        user_address_id=user_address_id,
        obj_in=user_address_in,
    )


@router.delete("/{user_address_id}")
async def delete_user_address(
    db: Annotated[AsyncSession, Depends(get_db)], user_address_id: int
) -> str:
    await remove(db, user_address_id=user_address_id)
    return "Eliminado"
