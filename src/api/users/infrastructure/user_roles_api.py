from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.user_roles_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import UserRoleCreate, UserRoleResponse, UserRoleUpdate
from src.core.db import get_db

router = APIRouter(tags=["user-roles"])


@router.get("/")
async def read_user_roles(
    db: Annotated[AsyncSession, Depends(get_db)], page: int = 0, shows: int = 100
) -> list[UserRoleResponse]:
    return await get_multi(db, page=page, shows=shows)


@router.get("/{user_role_id}")
async def read_user_role(
    db: Annotated[AsyncSession, Depends(get_db)], user_role_id: int
) -> UserRoleResponse:
    return await get_one(db, user_role_id)


@router.post("/")
async def create_user_role(
    db: Annotated[AsyncSession, Depends(get_db)], user_role_in: UserRoleCreate
) -> UserRoleResponse:
    return await create(db, obj_in=user_role_in)


@router.patch("/{user_role_id}")
async def update_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_role_id: int,
    user_role_in: UserRoleUpdate,
) -> UserRoleResponse:
    return await update(db, user_role_id=user_role_id, obj_in=user_role_in)


@router.delete("/{user_role_id}")
async def delete_user_role(
    db: Annotated[AsyncSession, Depends(get_db)], user_role_id: int
) -> str:
    await remove(db, user_role_id=user_role_id)
    return "Eliminado"
