from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserNotFound:
    user_id: int


@dataclass(frozen=True, slots=True)
class UserAddressNotFound:
    user_address_id: int


@dataclass(frozen=True, slots=True)
class UserRoleNotFound:
    user_role_id: int
