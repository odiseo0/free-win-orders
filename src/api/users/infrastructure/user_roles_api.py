from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.user_roles_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import (
    UserRoleCreate,
    UserRoleNotFound,
    UserRoleResponse,
    UserRoleUpdate,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.api.roles.domain import Actor, PermissionCode, SystemRoleIsImmutable
from src.api.roles.infrastructure.auth import require_actor

router = APIRouter(tags=["user-roles"], deprecated=True)


@router.get("/")
async def read_user_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    page: int = 0,
    shows: int = 100,
) -> list[UserRoleResponse]:
    result = await get_multi(db, page=page, shows=shows)

    match result:
        case Ok((user_roles, _)):
            return user_roles
        case Err(error):
            assert_never(error)


@router.get("/{user_role_id}")
async def read_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: int,
) -> UserRoleResponse:
    result = await get_one(db, user_role_id)

    match result:
        case Ok(user_role):
            return user_role
        case Err(UserRoleNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol del usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.post("/")
async def create_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_in: UserRoleCreate,
) -> UserRoleResponse:
    result = await create(db, obj_in=user_role_in)

    match result:
        case Ok(user_role):
            return user_role
        case Err(error):
            assert_never(error)


@router.patch("/{user_role_id}")
async def update_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: int,
    user_role_in: UserRoleUpdate,
) -> UserRoleResponse:
    result = await update(db, user_role_id=user_role_id, obj_in=user_role_in)

    match result:
        case Ok(user_role):
            return user_role
        case Err(UserRoleNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol del usuario no existe",
            )
        case Err(SystemRoleIsImmutable()):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Los roles del sistema son inmutables"
            )
        case unexpected:
            assert_never(unexpected)


@router.delete("/{user_role_id}")
async def delete_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: int,
) -> str:
    result = await remove(db, user_role_id=user_role_id)

    match result:
        case Ok():
            return "Eliminado"
        case Err(UserRoleNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol del usuario no existe",
            )
        case Err(SystemRoleIsImmutable()):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Los roles del sistema son inmutables"
            )
        case unexpected:
            assert_never(unexpected)
