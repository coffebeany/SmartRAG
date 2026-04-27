from __future__ import annotations

import time

import httpx

from app.clients.base import ClientResult, HealthCheckResult, ModelClientConfig


def _error_message(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


class OllamaClient:
    def __init__(self, config: ModelClientConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")

    async def chat(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> ClientResult:
        started = time.perf_counter()
        payload = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ClientResult(text=body.get("message", {}).get("content", ""), latency_ms=latency_ms, metadata={"resolved_model_name": body.get("model") or self.config.model_name})

    async def embedding(self, text: str) -> ClientResult:
        started = time.perf_counter()
        payload = {"model": self.config.model_name, "prompt": text}
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
            response.raise_for_status()
            body = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        embedding = body.get("embedding", [])
        return ClientResult(data=embedding, latency_ms=latency_ms, metadata={"embedding_dimension": len(embedding), "resolved_model_name": self.config.model_name})

    async def health_check(self) -> HealthCheckResult:
        try:
            if self.config.model_category == "embedding":
                result = await self.embedding("SmartRAG health check")
                return HealthCheckResult(status="available", latency_ms=result.latency_ms, metadata=result.metadata)
            result = await self.chat("Reply with OK.", temperature=0.0, max_tokens=8)
            return HealthCheckResult(status="available", latency_ms=result.latency_ms, metadata=result.metadata | {"supports_streaming": True})
        except Exception as exc:
            return HealthCheckResult(status="failed", error=_error_message(exc), metadata={})
