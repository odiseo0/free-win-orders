from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.users_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain.users import UserCreate, UserResponse, UserUpdate
from src.core.db import get_db

router = APIRouter(tags=["users"])


@router.get("/")
async def read_users(
    db: Annotated[AsyncSession, Depends(get_db)], page: int = 0, shows: int = 100
) -> list[UserResponse]:
    return await get_multi(db, page=page, shows=shows)


@router.get("/{user_id}")
async def read_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int
) -> UserResponse:
    return await get_one(db, user_id)


@router.post("/")
async def create_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_in: UserCreate
) -> UserResponse:
    return await create(db, obj_in=user_in)


@router.patch("/{user_id}")
async def update_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id, user_in: UserUpdate
) -> UserResponse:
    return await update(db, user_id=user_id, obj_in=user_in)


@router.delete("/{user_id}")
async def delete_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int
) -> str:
    await remove(db, user_id=user_id)
    return "Eliminado"
