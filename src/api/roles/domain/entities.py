from pydantic import Field

from src.core.schema import BaseModel

from .permissions import PermissionCode


class PermissionResponse(BaseModel):
    id: int
    code: PermissionCode
    description: str


class PermissionCreate(BaseModel):
    code: PermissionCode
    description: str


class PermissionUpdate(BaseModel):
    description: str | None = None


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleResponse(RoleBase):
    id: int
    is_system: bool
    permissions: list[PermissionResponse] = Field(default_factory=list)


class RolePermissionsUpdate(BaseModel):
    permissions: list[PermissionCode]
