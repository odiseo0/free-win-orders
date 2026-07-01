from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_prefix="API_", env_file=".env", extra="ignore"
    )


api_settings = APISettings()
