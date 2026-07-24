from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.roles.domain import (
    Actor,
    PermissionCode,
    require_owner_or_permission,
    require_permission,
)
from src.api.roles.infrastructure.auth import enforce_decision, get_current_user
from src.api.users.application.user_address_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import (
    UserAddressCreate,
    UserAddressListResponse,
    UserAddressNotFound,
    UserAddressResponse,
    UserAddressUpdate,
)
from src.core import Err, Ok
from src.core.db import get_db
from src.core.schema import (
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)

router = APIRouter(tags=["user-addresses"])

type UserAddressId = Annotated[
    int,
    Path(gt=0, description="Identificador positivo de la dirección del usuario."),
]

_AUTH_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    422: VALIDATION_RESPONSE,
}
_ADDRESS_NOT_FOUND_RESPONSE = {
    **NOT_FOUND_RESPONSE,
    "description": "La dirección del usuario no existe.",
}


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=UserAddressListResponse,
    operation_id="listUserAddresses",
    summary="Listar direcciones visibles",
    description=(
        "Devuelve solo las direcciones propias con permiso personal, o todas con "
        "permiso global, junto con el total disponible."
    ),
    responses=_AUTH_RESPONSES,
)
async def read_user_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    page: Annotated[
        int,
        Query(ge=1, description="Página solicitada; comienza en 1."),
    ] = 1,
    shows: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Cantidad máxima de direcciones por página.",
        ),
    ] = 100,
) -> UserAddressListResponse:
    filters = None
    if PermissionCode.ADDRESSES_READ_ANY not in actor.permissions:
        enforce_decision(require_permission(actor, PermissionCode.ADDRESSES_READ_SELF))
        filters = {"user_id": actor.user_id}
    result = await get_multi(db, page=page, shows=shows, filters=filters)

    match result:
        case Ok((user_addresses, total)):
            return UserAddressListResponse(items=user_addresses, total=total)
        case Err(error):
            assert_never(error)


@router.get(
    "/{user_address_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserAddressResponse,
    operation_id="getUserAddress",
    summary="Consultar una dirección",
    description=(
        "Permite consultar una dirección propia con permiso personal o cualquier "
        "dirección con permiso global."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ADDRESS_NOT_FOUND_RESPONSE,
    },
)
async def read_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: UserAddressId,
) -> UserAddressResponse:
    result = await get_one(db, user_address_id)

    match result:
        case Ok(user_address):
            enforce_decision(
                require_owner_or_permission(
                    actor,
                    user_address.user_id,
                    own_permission=PermissionCode.ADDRESSES_READ_SELF,
                    any_permission=PermissionCode.ADDRESSES_READ_ANY,
                )
            )
            return user_address
        case Err(UserAddressNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La dirección del usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserAddressResponse,
    operation_id="createUserAddress",
    summary="Crear una dirección",
    description=(
        "Crea una dirección propia con permiso personal o una dirección ajena con "
        "permiso global."
    ),
    responses=_AUTH_RESPONSES,
)
async def create_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_in: UserAddressCreate,
) -> UserAddressResponse:
    enforce_decision(
        require_owner_or_permission(
            actor,
            user_address_in.user_id,
            own_permission=PermissionCode.ADDRESSES_CREATE_SELF,
            any_permission=PermissionCode.ADDRESSES_CREATE_ANY,
        )
    )
    result = await create(db, obj_in=user_address_in)

    match result:
        case Ok(user_address):
            return user_address
        case Err(error):
            assert_never(error)


@router.patch(
    "/{user_address_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserAddressResponse,
    operation_id="updateUserAddress",
    summary="Actualizar una dirección",
    description=(
        "Actualiza una dirección propia o, con permiso global, cualquier dirección. "
        "Cambiar su propietario también requiere alcance global."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ADDRESS_NOT_FOUND_RESPONSE,
    },
)
async def update_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: UserAddressId,
    user_address_in: UserAddressUpdate,
) -> UserAddressResponse:
    current = await get_one(db, user_address_id)

    match current:
        case Err(UserAddressNotFound()):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La dirección no existe")
        case Ok(address):
            enforce_decision(
                require_owner_or_permission(
                    actor,
                    address.user_id,
                    own_permission=PermissionCode.ADDRESSES_UPDATE_SELF,
                    any_permission=PermissionCode.ADDRESSES_UPDATE_ANY,
                )
            )

            if user_address_in.user_id not in (None, address.user_id):
                enforce_decision(
                    require_permission(actor, PermissionCode.ADDRESSES_UPDATE_ANY)
                )
        case unexpected:
            assert_never(unexpected)

    result = await update(
        db,
        user_address_id=user_address_id,
        obj_in=user_address_in,
    )

    match result:
        case Ok(user_address):
            return user_address
        case Err(UserAddressNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La dirección del usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)


@router.delete(
    "/{user_address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="deleteUserAddress",
    summary="Eliminar una dirección",
    description=(
        "Elimina una dirección propia o, con permiso global, cualquier dirección, "
        "y responde sin cuerpo."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: _ADDRESS_NOT_FOUND_RESPONSE,
    },
)
async def delete_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: UserAddressId,
) -> Response:
    current = await get_one(db, user_address_id)

    match current:
        case Err(UserAddressNotFound()):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La dirección no existe")
        case Ok(address):
            enforce_decision(
                require_owner_or_permission(
                    actor,
                    address.user_id,
                    own_permission=PermissionCode.ADDRESSES_DELETE_SELF,
                    any_permission=PermissionCode.ADDRESSES_DELETE_ANY,
                )
            )
        case unexpected:
            assert_never(unexpected)

    result = await remove(db, user_address_id=user_address_id)

    match result:
        case Ok():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Err(UserAddressNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La dirección del usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)
