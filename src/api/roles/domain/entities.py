from pydantic import Field

from src.core.schema import BaseModel

from .permissions import PermissionCode


class PermissionResponse(BaseModel):
    id: int = Field(description="Identificador interno del permiso.")
    code: str = Field(
        description=(
            "Código estable persistido en la tabla compartida. Puede pertenecer "
            "a Free Win o a otro servicio."
        )
    )
    description: str = Field(description="Explicación del permiso.")


class PermissionCreate(BaseModel):
    code: PermissionCode = Field(description="Código estable del permiso.")
    description: str = Field(description="Explicación del permiso.")


class PermissionUpdate(BaseModel):
    description: str | None = Field(
        default=None, description="Nueva explicación del permiso."
    )


class RoleBase(BaseModel):
    name: str = Field(description="Nombre único del rol.")
    description: str | None = Field(
        default=None, description="Explicación opcional del rol."
    )


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, description="Nuevo nombre del rol.")
    description: str | None = Field(
        default=None, description="Nueva explicación del rol."
    )


class RoleResponse(RoleBase):
    id: int = Field(description="Identificador interno del rol.")
    is_system: bool = Field(
        description=(
            "Indica si Free Win administra el rol como inmutable y no eliminable."
        )
    )
    permissions: list[PermissionResponse] = Field(
        default_factory=list,
        description="Permisos efectivos asignados al rol.",
    )


class RolePermissionsUpdate(BaseModel):
    permissions: list[PermissionCode] = Field(
        description="Conjunto completo de códigos que sustituirá la asignación actual."
    )
