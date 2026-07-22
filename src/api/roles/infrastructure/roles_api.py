from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.roles.application import (
    create,
    get_multi,
    get_one,
    get_permissions,
    remove,
    replace_permissions,
    update,
)
from src.api.roles.domain import (
    Actor,
    PermissionCode,
    PermissionResponse,
    RoleCreate,
    RoleIsAssigned,
    RoleNameAlreadyExists,
    RoleNotFound,
    RolePermissionsUpdate,
    RoleResponse,
    RoleUpdate,
    SystemRoleIsImmutable,
)
from src.core import Err, Ok
from src.core.db import get_db

from .auth import require_actor

roles_router = APIRouter(tags=["roles"])
permissions_router = APIRouter(tags=["permissions"])

type RoleError = (
    RoleNotFound
    | RoleNameAlreadyExists
    | SystemRoleIsImmutable
    | RoleIsAssigned
)


def _raise_role_error(error: RoleError) -> None:
    match error:
        case RoleNotFound():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El rol no existe")
        case RoleNameAlreadyExists():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El nombre del rol ya existe",
            )
        case SystemRoleIsImmutable():
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Los roles del sistema son inmutables"
            )
        case RoleIsAssigned():
            raise HTTPException(
                status.HTTP_409_CONFLICT, "El rol está asignado a uno o más usuarios"
            )
        case unexpected:
            assert_never(unexpected)


@roles_router.get("/", response_model=list[RoleResponse])
async def read_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_READ))],
) -> list[RoleResponse]:
    result = await get_multi(db)

    match result:
        case Ok(roles):
            return roles
        case Err(error):
            assert_never(error)


@roles_router.get("/{role_id}", response_model=RoleResponse)
async def read_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_READ))],
    role_id: int,
) -> RoleResponse:
    result = await get_one(db, role_id)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@roles_router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_CREATE))],
    role_in: RoleCreate,
) -> RoleResponse:
    result = await create(db, role_in)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@roles_router.patch("/{role_id}", response_model=RoleResponse)
async def update_existing_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_UPDATE))],
    role_id: int,
    role_in: RoleUpdate,
) -> RoleResponse:
    result = await update(db, role_id, role_in)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_DELETE))],
    role_id: int,
) -> Response:
    result = await remove(db, role_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Err(error):
            _raise_role_error(error)


@roles_router.put("/{role_id}/permissions", response_model=RoleResponse)
async def set_role_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[
        Actor, Depends(require_actor(PermissionCode.ROLES_ASSIGN_PERMISSIONS))
    ],
    role_id: int,
    permissions_in: RolePermissionsUpdate,
) -> RoleResponse:
    result = await replace_permissions(db, role_id, permissions_in.permissions)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@permissions_router.get("/", response_model=list[PermissionResponse])
async def read_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.PERMISSIONS_READ))],
) -> list[PermissionResponse]:
    result = await get_permissions(db)

    match result:
        case Ok(permissions):
            return permissions
        case Err(error):
            assert_never(error)
