from __future__ import annotations

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartRAG API"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    database_url: str = "postgresql+asyncpg://smartrag:smartrag@127.0.0.1:5432/smartrag"
    secret_key: str = Field(default="change-me-to-a-long-random-string", min_length=8)
    material_storage_root: str = "storage/materials"
    parse_artifact_root: str = "storage/parsed"
    chunk_artifact_root: str = "storage/chunks"

    @cached_property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


settings = Settings()
