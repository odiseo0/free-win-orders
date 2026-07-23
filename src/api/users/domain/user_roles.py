from pydantic import Field

from src.core.schema import BaseModel, PaginatedResponse


class UserRole(BaseModel):
    role_id: int | None = Field(default=None, description="Rol asociado.")


class UserRoleCreate(UserRole):
    role_id: int = Field(description="Rol asociado.")


class UserRoleUpdate(UserRole):
    pass


class UserRoleResponse(UserRole):
    id: int = Field(description="Identificador del puente heredado.")


class UserRoleListResponse(PaginatedResponse[UserRoleResponse]):
    pass
