from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    DB_HOST: str
    DB_NAME: str
    DB_PORT: int
    DB_USERNAME: str
    DB_PASSWORD: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


db_settings = DBSettings()
