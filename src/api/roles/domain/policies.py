from dataclasses import dataclass
from enum import StrEnum

from .permissions import PermissionCode


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: int
    permissions: frozenset[PermissionCode]


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    FORBIDDEN = "forbidden"
    HIDDEN = "hidden"


def require_permission(
    actor: Actor, permission: PermissionCode
) -> AuthorizationDecision:
    if permission in actor.permissions:
        return AuthorizationDecision.ALLOW

    return AuthorizationDecision.FORBIDDEN


def require_owner_or_permission(
    actor: Actor,
    owner_id: int,
    *,
    own_permission: PermissionCode,
    any_permission: PermissionCode,
) -> AuthorizationDecision:
    if any_permission in actor.permissions:
        return AuthorizationDecision.ALLOW

    if actor.user_id == owner_id and own_permission in actor.permissions:
        return AuthorizationDecision.ALLOW

    return AuthorizationDecision.HIDDEN
