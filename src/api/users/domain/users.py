from pydantic import Field

from src.core.schema import BaseModel, PaginatedResponse


class User(BaseModel):
    external_id: str | None = Field(
        default=None, description="Identificador de un sistema externo, si existe."
    )
    first_name: str | None = Field(default=None, description="Nombre del usuario.")
    last_name: str | None = Field(default=None, description="Apellido del usuario.")
    alias: str | None = Field(
        default=None, description="Nombre público opcional del usuario."
    )
    email: str | None = Field(
        default=None, description="Correo de contacto del usuario."
    )
    phone_number: str | None = Field(
        default=None, description="Número telefónico sin el código internacional."
    )
    phone_code: str | None = Field(
        default=None, description="Código telefónico internacional."
    )
    id_number: str | None = Field(
        default=None,
        description="Documento de identificación usado para la entrega, si se requiere.",
    )


class UserCreate(User):
    first_name: str = Field(default=..., description="Nombre del usuario.")
    last_name: str = Field(default=..., description="Apellido del usuario.")
    email: str = Field(default=..., description="Correo de contacto del usuario.")
    password: str = Field(
        description=(
            "Contraseña recibida por el flujo temporal actual. Nunca se incluye en "
            "las respuestas; su endurecimiento permanece pendiente."
        ),
        json_schema_extra={"writeOnly": True},
    )

    model_config = {**BaseModel.model_config, "extra": "forbid"}


class UserUpdate(User):
    password: str | None = Field(
        default=None,
        description=(
            "Nueva contraseña para el flujo temporal actual. Se acepta solo como "
            "entrada y nunca se devuelve."
        ),
        json_schema_extra={"writeOnly": True},
    )


class UserResponse(User):
    id: int = Field(description="Identificador interno del usuario.")


class UserListResponse(PaginatedResponse[UserResponse]):
    pass


class UserRoleAssignment(BaseModel):
    role_id: int = Field(description="Rol que sustituirá la asignación actual.")
