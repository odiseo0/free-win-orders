from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    mode: Literal["disabled", "local"] = "disabled"
    local_user_id: int | None = None

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AUTH_", extra="ignore"
    )


auth_settings = AuthSettings()
