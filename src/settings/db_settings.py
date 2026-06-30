from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./free-win.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


db_settings = DbSettings()
