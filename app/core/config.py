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

    temp_upload_dir: str = "./temporary_uploads"
    workspace_ttl_hours: int = 24

    llm_provider_mode: Literal["mock", "external"] = "mock"
    llm_api_key: SecretStr | None = None

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