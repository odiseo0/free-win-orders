from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users.application.user_address_cases import (
    create,
    get_multi,
    get_one,
    remove,
    update,
)
from src.api.users.domain import (
    UserAddressCreate,
    UserAddressNotFound,
    UserAddressResponse,
    UserAddressUpdate,
)
from src.api.roles.domain import (
    Actor,
    PermissionCode,
    require_owner_or_permission,
    require_permission,
)
from src.api.roles.infrastructure.auth import enforce_decision, get_current_user
from src.core import Err, Ok
from src.core.db import get_db

router = APIRouter(tags=["user-addresses"])


@router.get("/")
async def read_user_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    page: int = 0,
    shows: int = 100,
) -> list[UserAddressResponse]:
    filters = None
    if PermissionCode.ADDRESSES_READ_ANY not in actor.permissions:
        enforce_decision(require_permission(actor, PermissionCode.ADDRESSES_READ_SELF))
        filters = {"user_id": actor.user_id}
    result = await get_multi(db, page=page, shows=shows, filters=filters)

    match result:
        case Ok((user_addresses, _)):
            return user_addresses
        case Err(error):
            assert_never(error)


@router.get("/{user_address_id}")
async def read_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: int,
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


@router.post("/")
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


@router.patch("/{user_address_id}")
async def update_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: int,
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


@router.delete("/{user_address_id}")
async def delete_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[Actor, Depends(get_current_user)],
    user_address_id: int,
) -> str:
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
            return "Eliminado"
        case Err(UserAddressNotFound()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La dirección del usuario no existe",
            )
        case unexpected:
            assert_never(unexpected)
