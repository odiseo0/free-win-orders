from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
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
from src.core.schema import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)

from .auth import require_actor

roles_router = APIRouter(tags=["roles"])
permissions_router = APIRouter(tags=["permissions"])

type RoleId = Annotated[
    int,
    Path(gt=0, description="Identificador positivo del rol."),
]

_AUTH_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
}
_ROLE_NOT_FOUND_RESPONSE = {
    **NOT_FOUND_RESPONSE,
    "description": "El rol no existe.",
}
_ROLE_CONFLICT_RESPONSE = {
    **CONFLICT_RESPONSE,
    "description": (
        "El nombre ya existe, el rol es del sistema o todavía tiene usuarios "
        "asignados, según la operación."
    ),
}

type RoleError = (
    RoleNotFound | RoleNameAlreadyExists | SystemRoleIsImmutable | RoleIsAssigned
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


@roles_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[RoleResponse],
    operation_id="listRoles",
    summary="Listar roles",
    description=(
        "Devuelve el catálogo completo de roles con sus permisos. No es un listado "
        "paginado."
    ),
    responses=_AUTH_RESPONSES,
)
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


@roles_router.get(
    "/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=RoleResponse,
    operation_id="getRole",
    summary="Consultar un rol",
    description="Devuelve un rol y todos sus permisos asignados.",
    responses={
        **_AUTH_RESPONSES,
        404: _ROLE_NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
async def read_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_READ))],
    role_id: RoleId,
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
    operation_id="createRole",
    summary="Crear un rol",
    description=(
        "Crea un rol administrable con nombre único y sin permisos asignados."
    ),
    responses={
        **_AUTH_RESPONSES,
        409: {
            **CONFLICT_RESPONSE,
            "description": "Ya existe un rol con el mismo nombre.",
        },
        422: VALIDATION_RESPONSE,
    },
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


@roles_router.patch(
    "/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=RoleResponse,
    operation_id="updateRole",
    summary="Actualizar un rol",
    description=(
        "Actualiza un rol administrable. Los roles del sistema son inmutables y los "
        "nombres no pueden repetirse."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ROLE_NOT_FOUND_RESPONSE,
        409: _ROLE_CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
async def update_existing_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_UPDATE))],
    role_id: RoleId,
    role_in: RoleUpdate,
) -> RoleResponse:
    result = await update(db, role_id, role_in)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@roles_router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="deleteRole",
    summary="Eliminar un rol",
    description=(
        "Elimina un rol administrable sin usuarios asignados. Los roles del sistema "
        "no pueden eliminarse."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ROLE_NOT_FOUND_RESPONSE,
        409: _ROLE_CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
async def remove_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.ROLES_DELETE))],
    role_id: RoleId,
) -> Response:
    result = await remove(db, role_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Err(error):
            _raise_role_error(error)


@roles_router.put(
    "/{role_id}/permissions",
    status_code=status.HTTP_200_OK,
    response_model=RoleResponse,
    operation_id="replaceRolePermissions",
    summary="Reemplazar los permisos de un rol",
    description=(
        "Sustituye el conjunto completo de permisos de un rol administrable mediante "
        "códigos estables. Los roles del sistema son inmutables."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ROLE_NOT_FOUND_RESPONSE,
        409: {
            **CONFLICT_RESPONSE,
            "description": "El rol pertenece al sistema y es inmutable.",
        },
        422: VALIDATION_RESPONSE,
    },
)
async def set_role_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[
        Actor, Depends(require_actor(PermissionCode.ROLES_ASSIGN_PERMISSIONS))
    ],
    role_id: RoleId,
    permissions_in: RolePermissionsUpdate,
) -> RoleResponse:
    result = await replace_permissions(db, role_id, permissions_in.permissions)

    match result:
        case Ok(role):
            return role
        case Err(error):
            _raise_role_error(error)


@permissions_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[PermissionResponse],
    operation_id="listPermissions",
    summary="Listar permisos",
    description=(
        "Devuelve el catálogo completo y no paginado de permisos reconocidos por el "
        "backend. Cada código expresa el recurso, la acción y, cuando aplica, el "
        "alcance propio o global."
    ),
    responses=_AUTH_RESPONSES,
)
async def read_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PermissionResponse]:
    result = await get_permissions(db)

    match result:
        case Ok(permissions):
            return permissions
        case Err(error):
            assert_never(error)
