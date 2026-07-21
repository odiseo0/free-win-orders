from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.users_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import UserNotFound
from src.api.users.domain.users import UserCreate, UserResponse, UserUpdate
from src.core import Err, Ok
from src.core.db import get_db

router = APIRouter(tags=["users"])


@router.get("/")
async def read_users(
    db: Annotated[AsyncSession, Depends(get_db)], page: int = 0, shows: int = 100
) -> list[UserResponse]:
    result = await get_multi(db, page=page, shows=shows)

    match result:
        case Ok((users, _)):
            return users
        case Err(error):
            assert_never(error)


@router.get("/{user_id}")
async def read_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int
) -> UserResponse:
    result = await get_one(db, user_id)

    match result:
        case Ok(user):
            return user
        case Err(UserNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.post("/")
async def create_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_in: UserCreate
) -> UserResponse:
    result = await create(db, obj_in=user_in)

    match result:
        case Ok(user):
            return user
        case Err(error):
            assert_never(error)


@router.patch("/{user_id}")
async def update_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int, user_in: UserUpdate
) -> UserResponse:
    result = await update(db, user_id=user_id, obj_in=user_in)

    match result:
        case Ok(user):
            return user
        case Err(UserNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.delete("/{user_id}")
async def delete_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_id: int
) -> str:
    result = await remove(db, user_id=user_id)

    match result:
        case Ok():
            return "Eliminado"
        case Err(UserNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)
