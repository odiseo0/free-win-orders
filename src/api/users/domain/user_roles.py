from src.core.schema import BaseModel


class UserRole(BaseModel):
    role_id: int | None = None


class UserRoleCreate(UserRole):
    role_id: int


class UserRoleUpdate(UserRole):
    pass


class UserRoleResponse(UserRole):
    id: int
