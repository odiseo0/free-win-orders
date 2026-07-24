from typing import ClassVar

from pydantic import Field

from src.core.schema import BaseModel, PaginatedResponse


class UserAddress(BaseModel):
    user_id: int | None = Field(
        default=None, description="Usuario propietario de la dirección."
    )
    name: str | None = Field(
        default=None, description="Nombre reconocible para la dirección."
    )
    latitude: float | None = Field(
        default=None, description="Latitud opcional para ubicación y entrega."
    )
    longitude: float | None = Field(
        default=None, description="Longitud opcional para ubicación y entrega."
    )
    state: str | None = Field(default=None, description="Estado o región.")
    city: str | None = Field(default=None, description="Ciudad.")
    address: str | None = Field(default=None, description="Dirección principal.")
    address_2: str | None = Field(
        default=None, description="Referencia o complemento opcional."
    )
    zip_code: str | None = Field(default=None, description="Código postal.")


class UserAddressCreate(UserAddress):
    user_id: int = Field(
        default=..., description="Usuario propietario de la dirección."
    )
    name: str = Field(default=..., description="Nombre reconocible para la dirección.")
    state: str = Field(default=..., description="Estado o región.")
    city: str = Field(default=..., description="Ciudad.")
    address: str = Field(default=..., description="Dirección principal.")
    zip_code: str = Field(default=..., description="Código postal.")

    model_config: ClassVar = {**BaseModel.model_config, "extra": "forbid"}


class UserAddressUpdate(UserAddress):
    pass


class UserAddressResponse(UserAddress):
    id: int = Field(description="Identificador interno de la dirección.")


class UserAddressListResponse(PaginatedResponse[UserAddressResponse]):
    pass
