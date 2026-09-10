from pydantic_settings import BaseSettings, SettingsConfigDict


class DeliverySettings(BaseSettings):
    poll_interval_seconds: int = 1800
    manual_refresh_cooldown_seconds: int = 300
    provider_timeout_seconds: int = 15
    max_backoff_seconds: int = 21600
    worker_idle_seconds: int = 10
    batch_size: int = 20

    model_config = SettingsConfigDict(
        env_prefix="DELIVERY_", env_file=".env", extra="ignore"
    )


delivery_settings = DeliverySettings()
