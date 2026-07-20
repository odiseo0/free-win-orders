from src.core.schema import BaseModel


class UserAddress(BaseModel):
    user_id: int | None = None
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    address_2: str | None = None
    zip_code: str | None = None


class UserAddressCreate(UserAddress):
    user_id: int
    name: str
    state: str
    city: str
    address: str
    zip_code: str


class UserAddressUpdate(UserAddress):
    pass


class UserAddressResponse(UserAddress):
    id: int
