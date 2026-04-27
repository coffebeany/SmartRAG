from __future__ import annotations

from app.clients.base import ModelClient, ModelClientConfig
from app.clients.ollama import OllamaClient
from app.clients.openai_compatible import OpenAICompatibleClient


def create_model_client(config: ModelClientConfig) -> ModelClient:
    if config.provider == "ollama":
        return OllamaClient(config)
    return OpenAICompatibleClient(config)

