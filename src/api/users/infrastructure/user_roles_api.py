from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
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
    UserRoleListResponse,
    UserRoleNotFound,
    UserRoleResponse,
    UserRoleUpdate,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.api.roles.domain import Actor, PermissionCode, SystemRoleIsImmutable
from src.api.roles.infrastructure.auth import require_actor

router = APIRouter(tags=["user-roles"], deprecated=True)

type UserRoleId = Annotated[
    int,
    Path(gt=0, description="Identificador positivo del puente de rol heredado."),
]


@router.get("/", response_model=UserRoleListResponse)
async def read_user_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    page: Annotated[int, Query(ge=1)] = 1,
    shows: Annotated[int, Query(ge=1, le=100)] = 100,
) -> UserRoleListResponse:
    result = await get_multi(db, page=page, shows=shows)

    match result:
        case Ok((user_roles, total)):
            return UserRoleListResponse(items=user_roles, total=total)
        case Err(error):
            assert_never(error)


@router.get("/{user_role_id}", response_model=UserRoleResponse)
async def read_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: UserRoleId,
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


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRoleResponse,
)
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


@router.patch("/{user_role_id}", response_model=UserRoleResponse)
async def update_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: UserRoleId,
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


@router.delete(
    "/{user_role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_role_id: UserRoleId,
) -> Response:
    result = await remove(db, user_role_id=user_role_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
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
