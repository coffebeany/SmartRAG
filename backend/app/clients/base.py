from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ModelClientConfig:
    provider: str
    base_url: str
    model_name: str
    model_category: str
    api_key: str | None
    timeout_seconds: int
    max_retries: int


@dataclass
class ClientResult:
    text: str | None = None
    data: dict | list | None = None
    latency_ms: int | None = None
    token_usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    status: str
    latency_ms: int | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class ModelClient(Protocol):
    async def chat(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> ClientResult:
        ...

    async def embedding(self, text: str) -> ClientResult:
        ...

    async def health_check(self) -> HealthCheckResult:
        ...

