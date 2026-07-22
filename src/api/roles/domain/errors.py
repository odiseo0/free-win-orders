from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleNotFound:
    role_id: int


@dataclass(frozen=True, slots=True)
class RoleNameAlreadyExists:
    name: str


@dataclass(frozen=True, slots=True)
class SystemRoleIsImmutable:
    role_id: int


@dataclass(frozen=True, slots=True)
class RoleIsAssigned:
    role_id: int


@dataclass(frozen=True, slots=True)
class UserNotFoundForPromotion:
    user_id: int
