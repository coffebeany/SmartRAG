from __future__ import annotations

import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.clients.base import ClientResult, HealthCheckResult, ModelClientConfig


def _error_message(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


class OpenAICompatibleClient:
    def __init__(self, config: ModelClientConfig) -> None:
        self.config = config
        self.base_url = config.base_url.strip().rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.strip()}"
        return headers

    def _endpoint_url(self, endpoint: str) -> str:
        """Accept either an OpenAI-compatible root URL or a full endpoint URL."""
        endpoint = endpoint.strip("/")
        parsed = urlsplit(self.base_url)
        path = parsed.path.rstrip("/")
        if path.endswith(f"/{endpoint}") or path == f"/{endpoint}":
            return self.base_url
        return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/{endpoint}", parsed.query, parsed.fragment))

    def _root_url(self) -> str:
        parsed = urlsplit(self.base_url)
        path = parsed.path.rstrip("/")
        for suffix in ["/chat/completions", "/embeddings"]:
            if path.endswith(suffix):
                path = path[: -len(suffix)] or "/"
                break
        return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), parsed.query, parsed.fragment)).rstrip("/")

    def _model_traits(self) -> list[str]:
        model_name = self.config.model_name.lower()
        traits: list[str] = []
        if any(marker in model_name for marker in ["reason", "r1", "qwq", "o1", "o3", "o4"]):
            traits.append("reasoning_inferred")
        if any(marker in model_name for marker in ["qwen3", "qwen2.5", "deepseek", "glm", "yi"]):
            traits.append("multilingual_inferred")
        return traits

    @staticmethod
    def _first_int(data: dict, keys: list[str]) -> int | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _extract_model_info(self, model_info: dict | None) -> dict:
        if not model_info:
            return {"model_info_status": "unavailable"}
        return {
            "model_info_status": "available",
            "model_info_fields": sorted(model_info.keys()),
            "context_window": self._first_int(
                model_info,
                ["context_window", "context_length", "max_context_length", "max_context_tokens"],
            ),
            "max_output_tokens": self._first_int(
                model_info,
                ["max_output_tokens", "max_completion_tokens", "max_tokens"],
            ),
            "model_info_owned_by": model_info.get("owned_by"),
            "model_info_object": model_info.get("object"),
        }

    def _timeout(self) -> httpx.Timeout:
        timeout = float(self.config.timeout_seconds)
        return httpx.Timeout(timeout=timeout, connect=min(10.0, timeout), read=timeout)

    async def _post_json(self, url: str, payload: dict) -> dict:
        attempts = max(1, self.config.max_retries + 1)

        @retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
            reraise=True,
        )
        async def do_post() -> dict:
            async with httpx.AsyncClient(
                timeout=self._timeout(),
                trust_env=False,
                http2=False,
                follow_redirects=True,
                headers={"User-Agent": "SmartRAG/0.1"},
            ) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
                return response.json()

        return await do_post()

    async def _get_json(self, url: str) -> dict:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=min(float(self.config.timeout_seconds), 10.0), connect=5.0),
            trust_env=False,
            http2=False,
            follow_redirects=True,
            headers={"User-Agent": "SmartRAG/0.1"},
        ) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def _fetch_model_info(self) -> dict | None:
        models_url = self._endpoint_url("models") if not self.base_url.endswith("/models") else self.base_url
        if "/chat/completions" in models_url or "/embeddings" in models_url:
            models_url = f"{self._root_url()}/models"
        try:
            body = await self._get_json(models_url)
        except Exception:
            return None
        model_name = self.config.model_name.strip()
        models = body.get("data")
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict) and item.get("id") == model_name:
                    return item
        return body if isinstance(body, dict) else None

    async def chat(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> ClientResult:
        started = time.perf_counter()
        payload: dict = {
            "model": self.config.model_name.strip(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        endpoint_url = self._endpoint_url("chat/completions")
        body = await self._post_json(endpoint_url, payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = body.get("choices") if isinstance(body.get("choices"), list) else []
        first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
        text = message.get("content", "")
        usage = body.get("usage") or {}
        return ClientResult(
            text=text,
            latency_ms=latency_ms,
            token_usage=usage,
            metadata={
                "resolved_model_name": body.get("model"),
                "response_id": body.get("id"),
                "response_object": body.get("object"),
                "response_created": body.get("created"),
                "response_fields": sorted(body.keys()),
                "choice_fields": sorted(first_choice.keys()),
                "message_fields": sorted(message.keys()),
                "finish_reason": first_choice.get("finish_reason"),
                "usage_fields": sorted(usage.keys()) if isinstance(usage, dict) else [],
                "token_usage": usage,
            },
        )

    async def embedding(self, text: str) -> ClientResult:
        started = time.perf_counter()
        payload = {"model": self.config.model_name.strip(), "input": text}
        endpoint_url = self._endpoint_url("embeddings")
        body = await self._post_json(endpoint_url, payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        embedding = body.get("data", [{}])[0].get("embedding", [])
        return ClientResult(data=embedding, latency_ms=latency_ms, token_usage=body.get("usage") or {}, metadata={"embedding_dimension": len(embedding), "resolved_model_name": body.get("model")})

    async def health_check(self) -> HealthCheckResult:
        try:
            if self.config.model_category == "embedding":
                result = await self.embedding("SmartRAG health check")
                return HealthCheckResult(status="available", latency_ms=result.latency_ms, metadata=result.metadata | {"supports_batch": True})
            result = await self.chat("Reply with OK.", temperature=0.0, max_tokens=8)
            model_info = self._extract_model_info(await self._fetch_model_info())
            return HealthCheckResult(
                status="available",
                latency_ms=result.latency_ms,
                metadata=result.metadata
                | model_info
                | {
                    "supports_chat_completions": True,
                    "supports_streaming": "not_tested",
                    "supports_reasoning": "inferred" if "reasoning_inferred" in self._model_traits() else "unknown",
                    "model_traits": self._model_traits(),
                    "capability_source": {
                        "chat_completions": "verified_by_request",
                        "streaming": "not_tested",
                        "reasoning": "model_name_heuristic",
                        "context_window": "models_endpoint_if_available",
                    },
                    "openai_compatible_schema_note": "Chat completion responses share a common shape, but provider-specific fields are not guaranteed.",
                    "endpoint_url": self._endpoint_url("chat/completions"),
                },
            )
        except Exception as exc:
            endpoint = "embeddings" if self.config.model_category == "embedding" else "chat/completions"
            return HealthCheckResult(
                status="failed",
                error=_error_message(exc),
                metadata={
                    "error_type": exc.__class__.__name__,
                    "endpoint_url": self._endpoint_url(endpoint),
                },
            )
