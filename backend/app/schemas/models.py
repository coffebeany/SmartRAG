from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ModelCategory = Literal["llm", "embedding", "reranker", "multimodal", "reasoning", "moe", "vision_embedding", "speech", "custom"]
Provider = Literal["openai_compatible", "ollama", "custom"]
ConnectionStatus = Literal["unknown", "checking", "available", "failed"]


class ModelBase(BaseModel):
    project_id: str | None = None
    display_name: str = Field(min_length=1, max_length=120)
    model_category: ModelCategory
    provider: Provider
    base_url: str
    model_name: str = Field(min_length=1, max_length=200)
    api_version: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    enabled: bool = True
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_streaming: bool | None = None
    supports_json_schema: bool | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_batch: bool | None = None
    model_traits: list[str] = Field(default_factory=list)
    pricing: dict | None = None


class ModelCreate(ModelBase):
    api_key: str | None = None


class ModelUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    model_category: ModelCategory | None = None
    provider: Provider | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    api_version: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    enabled: bool | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_streaming: bool | None = None
    supports_json_schema: bool | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_batch: bool | None = None
    model_traits: list[str] | None = None
    pricing: dict | None = None


class ModelOut(ModelBase):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    api_key_masked: str | None = None
    connection_status: ConnectionStatus
    last_check_at: datetime | None = None
    last_error: str | None = None
    resolved_model_name: str | None = None
    embedding_dimension: int | None = None
    created_at: datetime
    updated_at: datetime


class HealthCheckOut(BaseModel):
    status: ConnectionStatus
    latency_ms: int | None = None
    error: str | None = None
    response_metadata: dict = Field(default_factory=dict)


class ModelDefaultsOut(BaseModel):
    defaults: dict[str, str | None]


class ModelDefaultsUpdate(BaseModel):
    defaults: dict[str, str | None]


class ProviderInfo(BaseModel):
    provider: Provider
    display_name: str
    default_base_url: str
    supports_categories: list[ModelCategory]
