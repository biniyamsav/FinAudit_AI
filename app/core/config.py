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
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: SecretStr | None = None

    temp_upload_dir: str = "./temporary_uploads"
    workspace_ttl_hours: int = 24
    processing_stale_minutes: int = 15
    max_documents_per_workspace: int = 20
    max_workspace_bytes: int = 200_000_000
    extraction_timeout_seconds: int = 300
    upload_rate_limit_per_minute: int = 20
    cleanup_interval_minutes: int = 30
    chat_rate_limit_per_minute: int = 10
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    weaviate_host: str = "localhost"
    weaviate_http_port: int = 8080
    weaviate_grpc_port: int = 50051
    weaviate_secure: bool = False
    weaviate_api_key: SecretStr | None = None
    max_documents_per_workspace: int = 20
    max_workspace_bytes: int = 200_000_000
    extraction_timeout_seconds: int = 300
    upload_rate_limit_per_minute: int = 20
    cleanup_interval_minutes: int = 30

    extraction_max_pages: int = 200
    extraction_max_rows: int = 100_000
    extraction_max_cells: int = 500_000
    extraction_max_ocr_pages: int = 30

    llm_provider_mode: Literal["mock", "external"] = "mock"
    llm_api_key: SecretStr | None = None
    weaviate_url: str | None = None

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    def validate_for_startup(self) -> None:
        if self.environment == "production":
            if self.database_url is None:
                raise ValueError("DATABASE_URL is required in production.")
            if self.llm_api_key is None:
                raise ValueError("LLM_API_KEY is required in production.")
            if self.weaviate_url is None:
                raise ValueError("WEAVIATE_URL is required in production.")

@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()