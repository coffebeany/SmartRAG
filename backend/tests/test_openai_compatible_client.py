from __future__ import annotations

from app.clients.base import ModelClientConfig
from app.clients.openai_compatible import OpenAICompatibleClient


def make_client(base_url: str) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        ModelClientConfig(
            provider="openai_compatible",
            base_url=base_url,
            model_name="Qwen/Qwen3.5-4B",
            model_category="llm",
            api_key="sk-test",
            timeout_seconds=30,
            max_retries=0,
        )
    )


def test_chat_endpoint_accepts_root_base_url() -> None:
    client = make_client("https://api.siliconflow.cn/v1")

    assert client._endpoint_url("chat/completions") == "https://api.siliconflow.cn/v1/chat/completions"


def test_chat_endpoint_accepts_full_endpoint_url() -> None:
    client = make_client("https://api.siliconflow.cn/v1/chat/completions")

    assert client._endpoint_url("chat/completions") == "https://api.siliconflow.cn/v1/chat/completions"


def test_endpoint_keeps_query_string_when_appending() -> None:
    client = make_client("https://example.com/v1?api-version=2024-01-01")

    assert (
        client._endpoint_url("chat/completions")
        == "https://example.com/v1/chat/completions?api-version=2024-01-01"
    )


def test_root_url_strips_full_chat_endpoint() -> None:
    client = make_client("https://api.siliconflow.cn/v1/chat/completions")

    assert client._root_url() == "https://api.siliconflow.cn/v1"


def test_reasoning_trait_is_inferred_from_model_name() -> None:
    client = OpenAICompatibleClient(
        ModelClientConfig(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model_name="deepseek-ai/DeepSeek-R1",
            model_category="llm",
            api_key="sk-test",
            timeout_seconds=30,
            max_retries=0,
        )
    )

    assert "reasoning_inferred" in client._model_traits()
