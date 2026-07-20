from src.core.schema import BaseModel


class User(BaseModel):
    external_id: str | None = None
    role_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    alias: str | None = None
    email: str | None = None
    password: str | None = None
    phone_number: str | None = None
    phone_code: str | None = None
    id_number: str | None = None


class UserCreate(User):
    role_id: int = 1
    first_name: str
    last_name: str
    email: str
    password: str


class UserUpdate(User):
    pass


class UserResponse(User):
    id: int
