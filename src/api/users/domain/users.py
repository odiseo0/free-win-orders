from src.core.schema import BaseModel


class User(BaseModel):
    external_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    alias: str | None = None
    email: str | None = None
    phone_number: str | None = None
    phone_code: str | None = None
    id_number: str | None = None


class UserCreate(User):
    first_name: str
    last_name: str
    email: str
    password: str

    model_config = {**BaseModel.model_config, "extra": "forbid"}


class UserUpdate(User):
    password: str | None = None


class UserResponse(User):
    id: int


class UserRoleAssignment(BaseModel):
    role_id: int
