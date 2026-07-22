from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    DB_HOST: str
    DB_NAME: str
    DB_PORT: int
    DB_USERNAME: str
    DB_PASSWORD: str

    SQLALCHEMY_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: str | None, info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v

        return f"postgresql+asyncpg://{info.data['DB_USERNAME']}:{info.data['DB_PASSWORD']}@{info.data['DB_HOST']}:{info.data['DB_PORT']}/{info.data['DB_NAME']}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


db_settings = DBSettings()
