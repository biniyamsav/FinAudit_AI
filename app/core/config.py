from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "testing", "production"] = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: SecretStr | None = None

    object_storage_backend: Literal["local", "s3"] = "local"
    object_storage_path: str = "./temporary_uploads"
    object_storage_bucket: str | None = None
    object_storage_endpoint_url: str | None = None

    llm_provider_mode: Literal["mock", "external"] = "mock"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    def validate_for_startup(self) -> None:
        """Validate settings required to start the application."""

        if self.environment == "production" and self.database_url is None:
            raise ValueError(
                "DATABASE_URL is required when ENVIRONMENT is production."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()