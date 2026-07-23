from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.roles.domain import (
    Actor,
    AuthorizationDecision,
    PermissionCode,
    require_permission,
)
from src.api.roles.repository import dao_authorization
from src.core.db import get_db
from src.core.utils.utils import Empty
from src.settings.auth_settings import auth_settings


async def get_current_user(db: Annotated[AsyncSession, Depends(get_db)]) -> Actor:
    if auth_settings.mode != "local" or auth_settings.local_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No hay una identidad configurada",
        )

    actor_record = await dao_authorization.get_actor(db, auth_settings.local_user_id)

    if actor_record is Empty:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La identidad local no existe",
        )

    permissions = frozenset(
        PermissionCode(code) for code in actor_record.permission_codes
    )

    return Actor(user_id=actor_record.user_id, permissions=permissions)


def enforce_decision(decision: AuthorizationDecision) -> None:
    match decision:
        case AuthorizationDecision.ALLOW:
            return
        case AuthorizationDecision.FORBIDDEN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta operación",
            )
        case AuthorizationDecision.HIDDEN:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El recurso no existe",
            )


def require_actor(permission: PermissionCode) -> Callable[..., Actor]:
    async def dependency(actor: Annotated[Actor, Depends(get_current_user)]) -> Actor:
        if auth_settings.mode != "local" or auth_settings.local_user_id is None:
            enforce_decision(require_permission(actor, permission))

        return actor

    return dependency
