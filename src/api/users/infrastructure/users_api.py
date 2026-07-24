from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.roles.domain import (
    Actor,
    PermissionCode,
    RoleNotFound,
    require_owner_or_permission,
)
from src.api.roles.infrastructure.auth import (
    enforce_decision,
    get_current_user,
    require_actor,
)
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
    UserListResponse,
    UserResponse,
    UserRoleAssignment,
    UserUpdate,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.core.schema import (
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)

router = APIRouter(tags=["users"])

type UserId = Annotated[
    int,
    Path(gt=0, description="Identificador positivo del usuario."),
]

_AUTH_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    422: VALIDATION_RESPONSE,
}
_USER_NOT_FOUND_RESPONSE = {
    **NOT_FOUND_RESPONSE,
    "description": "El usuario no existe.",
}


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=UserListResponse,
    operation_id="listUsers",
    summary="Listar usuarios",
    description=(
        "Devuelve usuarios de todo Free Win con el total disponible. Requiere "
        "permiso global."
    ),
    responses=_AUTH_RESPONSES,
)
async def read_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_READ_ANY))],
    page: Annotated[
        int,
        Query(ge=1, description="Página solicitada; comienza en 1."),
    ] = 1,
    shows: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Cantidad máxima de usuarios por página.",
        ),
    ] = 100,
) -> UserListResponse:
    result = await get_multi(db, page=page, shows=shows)

    match result:
        case Ok((users, total)):
            return UserListResponse(items=users, total=total)
        case Err(error):
            assert_never(error)


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    operation_id="getUser",
    summary="Consultar un usuario",
    description=(
        "Permite consultar el usuario propio con permiso personal o cualquier usuario "
        "con permiso global. La respuesta nunca incluye la contraseña."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _USER_NOT_FOUND_RESPONSE,
    },
)
async def read_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_id: UserId,
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


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    operation_id="createUser",
    summary="Crear un usuario",
    description=(
        "Registra un usuario con el tratamiento temporal actual de contraseña. La "
        "contraseña es solo de entrada y nunca forma parte de la respuesta."
    ),
    responses={422: VALIDATION_RESPONSE},
)
async def create_user(
    db: Annotated[AsyncSession, Depends(get_db)], user_in: UserCreate
) -> UserResponse:
    result = await create(db, obj_in=user_in)

    match result:
        case Ok(user):
            return user
        case Err(error):
            assert_never(error)


@router.patch(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    operation_id="updateUser",
    summary="Actualizar un usuario",
    description=(
        "Permite actualizar el perfil propio con permiso personal o cualquier perfil "
        "con permiso global. Una contraseña enviada nunca se devuelve."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _USER_NOT_FOUND_RESPONSE,
    },
)
async def update_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_id: UserId,
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


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="deleteUser",
    summary="Eliminar un usuario",
    description=("Elimina un usuario con permiso global y responde sin cuerpo."),
    responses={
        **_AUTH_RESPONSES,
        404: _USER_NOT_FOUND_RESPONSE,
    },
)
async def delete_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_DELETE_ANY))],
    user_id: UserId,
) -> Response:
    result = await remove(db, user_id=user_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Err(UserNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.put(
    "/{user_id}/role",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    operation_id="setUserRole",
    summary="Asignar el rol de un usuario",
    description=(
        "Sustituye la asignación de rol del usuario. Requiere permiso global y usa "
        "el identificador real del rol."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: {
            **NOT_FOUND_RESPONSE,
            "description": "El usuario o el rol no existe.",
        },
    },
)
async def set_user_role(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Actor, Depends(require_actor(PermissionCode.USERS_ASSIGN_ROLE))],
    user_id: UserId,
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
