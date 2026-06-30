from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True

    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")


api_settings = ApiSettings()
