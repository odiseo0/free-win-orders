from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.users_cases import (
    assign_role,
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import UserNotFound
from src.api.users.domain.users import (
    UserCreate,
    UserResponse,
    UserRoleAssignment,
    UserUpdate,
)
from src.api.roles.domain import (
    Actor,
    PermissionCode,
    RoleNotFound,
    require_owner_or_permission,
)
from src.api.roles.infrastructure.auth import enforce_decision, get_current_user, require_actor
from src.core import Err, Ok
from src.core.db import get_db

router = APIRouter(tags=["users"])


@router.get("/")
async def read_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_READ_ANY))],
    page: int = 0,
    shows: int = 100,
) -> list[UserResponse]:
    result = await get_multi(db, page=page, shows=shows)

    match result:
        case Ok((users, _)):
            return users
        case Err(error):
            assert_never(error)


@router.get("/{user_id}")
async def read_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_id: int,
) -> UserResponse:
    enforce_decision(
        require_owner_or_permission(
            actor,
            user_id,
            own_permission=PermissionCode.USERS_READ_SELF,
            any_permission=PermissionCode.USERS_READ_ANY,
        )
    )
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


@router.post("/", status_code=status.HTTP_201_CREATED)
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
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_id: int,
    user_in: UserUpdate,
) -> UserResponse:
    enforce_decision(
        require_owner_or_permission(
            actor,
            user_id,
            own_permission=PermissionCode.USERS_UPDATE_SELF,
            any_permission=PermissionCode.USERS_UPDATE_ANY,
        )
    )
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
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_DELETE_ANY))],
    user_id: int,
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


@router.put("/{user_id}/role")
async def set_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_id: int,
    assignment: UserRoleAssignment,
) -> UserResponse:
    result = await assign_role(db, user_id, assignment.role_id)

    match result:
        case Ok(user):
            return user
        case Err(UserNotFound()):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El usuario no existe")
        case Err(RoleNotFound()):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El rol no existe")
        case unexpected:
            assert_never(unexpected)
