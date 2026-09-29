from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    cors_allowed_origins: list[str] = [
        "http://127.0.0.1:4321",
        "http://localhost:4321",
    ]

    model_config = SettingsConfigDict(
        env_prefix="API_", env_file=".env", extra="ignore"
    )


api_settings = APISettings()
