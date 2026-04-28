from __future__ import annotations

import json
import ast
import asyncio
import copy
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.clients.base import ModelClientConfig
from app.clients.factory import create_model_client
from app.clients.openai_compatible import OpenAICompatibleClient
from app.core.security import decrypt_secret
from app.models.entities import Chunk, ModelConnection


@dataclass
class NormalizedEvalSample:
    question: str
    ground_truth: str
    reference_contexts: list[str]
    source_chunk_ids: list[str]
    source_file_ids: list[str]
    synthesizer_name: str = "ragas_smart_prompt"
    item_metadata: dict[str, Any] = field(default_factory=dict)


def _config_for_model(model: ModelConnection) -> ModelClientConfig:
    return ModelClientConfig(
        provider=model.provider,
        base_url=model.base_url,
        model_name=model.model_name,
        model_category=model.model_category,
        api_key=decrypt_secret(model.api_key_encrypted),
        timeout_seconds=model.timeout_seconds,
        max_retries=model.max_retries,
    )


def _client_for_model(model: ModelConnection):
    return create_model_client(_config_for_model(model))


def _sync_chat_for_model(model: ModelConnection, prompt: str, *, temperature: float, max_tokens: int | None) -> str:
    config = _config_for_model(model)
    if config.provider == "ollama":
        payload: dict[str, Any] = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        with httpx.Client(timeout=config.timeout_seconds, trust_env=False) as client:
            response = client.post(f"{config.base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
        return str(body.get("message", {}).get("content") or "")

    client_config = OpenAICompatibleClient(config)
    payload: dict[str, Any] = {
        "model": config.model_name.strip(),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    with httpx.Client(
        timeout=client_config._timeout(),
        trust_env=False,
        http2=False,
        follow_redirects=True,
        headers={"User-Agent": "SmartRAG/0.1"},
    ) as client:
        response = client.post(client_config._endpoint_url("chat/completions"), headers=client_config._headers(), json=payload)
        response.raise_for_status()
        body = response.json()
    choices = body.get("choices") if isinstance(body.get("choices"), list) else []
    first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
    return str(message.get("content") or "")


def _sync_embedding_for_model(model: ModelConnection, text: str) -> list[float]:
    config = _config_for_model(model)
    if config.provider == "ollama":
        with httpx.Client(timeout=config.timeout_seconds, trust_env=False) as client:
            response = client.post(
                f"{config.base_url.rstrip('/')}/api/embeddings",
                json={"model": config.model_name, "prompt": text},
            )
            response.raise_for_status()
            body = response.json()
        return [float(value) for value in (body.get("embedding") or [])]

    client_config = OpenAICompatibleClient(config)
    with httpx.Client(
        timeout=client_config._timeout(),
        trust_env=False,
        http2=False,
        follow_redirects=True,
        headers={"User-Agent": "SmartRAG/0.1"},
    ) as client:
        response = client.post(
            client_config._endpoint_url("embeddings"),
            headers=client_config._headers(),
            json={"model": config.model_name.strip(), "input": text},
        )
        response.raise_for_status()
        body = response.json()
    embedding = body.get("data", [{}])[0].get("embedding", [])
    return [float(value) for value in embedding]


def _load_json_object(text: str) -> dict[str, Any] | None:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean.removeprefix("json").strip()
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _patch_ast_compat() -> None:
    # Some RAGAS dependency versions still reference pre-3.14 AST aliases.
    for alias in ("NameConstant", "Num", "Str", "Bytes", "Ellipsis"):
        if not hasattr(ast, alias):
            setattr(ast, alias, ast.Constant)


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Synchronous RAGAS model calls are not supported inside an active event loop.")


def _prompt_text(prompt: Any) -> str:
    if hasattr(prompt, "to_string"):
        return str(prompt.to_string())
    return str(prompt)


def _ragas_llm_for_model(model: ModelConnection):
    _patch_ast_compat()
    from langchain_core.outputs import Generation, LLMResult
    from ragas.llms.base import BaseRagasLLM

    class SmartRAGRagasLLM(BaseRagasLLM):
        def __init__(self, model_row: ModelConnection) -> None:
            super().__init__()
            self.model_row = model_row
            self.client = _client_for_model(model_row)

        async def agenerate_text(
            self,
            prompt: Any,
            n: int = 1,
            temperature: float | None = 0.01,
            stop: list[str] | None = None,
            callbacks: Any = None,
        ) -> LLMResult:
            text = _prompt_text(prompt)
            generations = []
            for _ in range(max(n, 1)):
                result = await self.client.chat(
                    text,
                    temperature=0.01 if temperature is None else float(temperature),
                    max_tokens=self.model_row.max_output_tokens,
                )
                generations.append(Generation(text=result.text or ""))
            return LLMResult(generations=[generations])

        def generate_text(
            self,
            prompt: Any,
            n: int = 1,
            temperature: float = 0.01,
            stop: list[str] | None = None,
            callbacks: Any = None,
        ) -> LLMResult:
            text = _prompt_text(prompt)
            generations = [
                Generation(
                    text=_sync_chat_for_model(
                        self.model_row,
                        text,
                        temperature=0.01 if temperature is None else float(temperature),
                        max_tokens=self.model_row.max_output_tokens,
                    )
                )
                for _ in range(max(n, 1))
            ]
            return LLMResult(generations=[generations])

        def is_finished(self, response: LLMResult) -> bool:
            return True

        def __repr__(self) -> str:
            return f"SmartRAGRagasLLM(model={self.model_row.display_name})"

    return SmartRAGRagasLLM(model)


def _ragas_embeddings_for_model(model: ModelConnection | None):
    if model is None:
        raise RuntimeError("embedding_model_id or default_embedding_model is required for RAGAS evaluation.")
    _patch_ast_compat()
    from ragas.embeddings.base import BaseRagasEmbeddings

    class SmartRAGRagasEmbeddings(BaseRagasEmbeddings):
        def __init__(self, model_row: ModelConnection) -> None:
            super().__init__()
            self.model_row = model_row
            self.client = _client_for_model(model_row)

        async def aembed_query(self, text: str) -> list[float]:
            result = await self.client.embedding(text)
            return [float(value) for value in (result.data or [])]

        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            return [await self.aembed_query(text) for text in texts]

        def embed_query(self, text: str) -> list[float]:
            return _sync_embedding_for_model(self.model_row, text)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [_sync_embedding_for_model(self.model_row, text) for text in texts]

        def __repr__(self) -> str:
            return f"SmartRAGRagasEmbeddings(model={self.model_row.display_name})"

    return SmartRAGRagasEmbeddings(model)


def _fresh_ragas_metrics(metric_ids: list[str], metric_map: dict[str, Any]) -> list[Any]:
    selected = []
    for metric_id in metric_ids:
        metric = metric_map.get(metric_id)
        if metric is not None:
            selected.append(copy.deepcopy(metric))
    return selected


def _bind_ragas_models(metrics: list[Any], *, llm: Any, embeddings: Any) -> None:
    for metric in metrics:
        if hasattr(metric, "llm"):
            metric.llm = llm
        if hasattr(metric, "embeddings"):
            metric.embeddings = embeddings


class RagasAdapter:
    framework_id = "ragas"

    def _patch_ast_compat(self) -> None:
        _patch_ast_compat()

    def _ensure_dependencies(self) -> None:
        self._patch_ast_compat()
        try:
            import ragas  # noqa: F401
            import datasets  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("RAGAS dependencies are not installed. Run `uv sync --extra eval-ragas`.") from exc

    async def generate_samples(
        self,
        *,
        chunks: list[Chunk],
        generator_config: dict[str, Any],
        judge_llm_model: ModelConnection,
        embedding_model: ModelConnection | None = None,
    ) -> list[NormalizedEvalSample]:
        self._ensure_dependencies()
        testset_size = int(generator_config.get("testset_size") or 10)
        language = str(generator_config.get("language") or "zh")
        llm_context = str(generator_config.get("llm_context") or "")
        persona = str(generator_config.get("persona") or "")
        client = _client_for_model(judge_llm_model)
        selected = chunks[: max(testset_size, 1)]
        samples: list[NormalizedEvalSample] = []
        for chunk in selected:
            prompt = (
                "You are generating a RAG evaluation dataset item. "
                "Return strict JSON with keys question and ground_truth only. "
                f"Language: {language}. "
                f"Persona: {persona or 'general user'}. "
                f"Application context: {llm_context or 'not specified'}.\n\n"
                f"Reference context:\n{chunk.contents[:6000]}"
            )
            result = await client.chat(prompt, temperature=0.2, max_tokens=512)
            parsed = _load_json_object(result.text or "")
            question = str((parsed or {}).get("question") or "").strip()
            ground_truth = str((parsed or {}).get("ground_truth") or "").strip()
            if not question:
                question = f"请根据材料回答：{chunk.contents[:80]}"
            if not ground_truth:
                ground_truth = chunk.contents[:1200]
            samples.append(
                NormalizedEvalSample(
                    question=question,
                    ground_truth=ground_truth,
                    reference_contexts=[chunk.contents],
                    source_chunk_ids=[chunk.chunk_id],
                    source_file_ids=[chunk.source_file_id],
                    item_metadata={
                        "framework": "ragas",
                        "generation_engine": "ragas_adapter_smart_prompt",
                        "embedding_model_id": embedding_model.model_id if embedding_model else None,
                    },
                )
            )
            if len(samples) >= testset_size:
                break
        return samples

    async def evaluate(
        self,
        *,
        records: list[dict[str, Any]],
        metric_ids: list[str],
        judge_llm_model: ModelConnection | None = None,
        embedding_model: ModelConnection | None = None,
    ) -> tuple[dict[str, float], list[dict[str, float]]]:
        self._ensure_dependencies()
        try:
            from datasets import Dataset
            from ragas import aevaluate
            from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
        except ImportError as exc:
            raise RuntimeError("RAGAS evaluation imports failed.") from exc

        metric_map = {
            "context_precision": context_precision,
            "context_recall": context_recall,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
        }
        selected = _fresh_ragas_metrics(metric_ids, metric_map)
        dataset = Dataset.from_list(
            [
                {
                    "question": item["question"],
                    "answer": item.get("answer") or "",
                    "contexts": item.get("contexts") or [],
                    "ground_truth": item.get("ground_truth") or "",
                }
                for item in records
            ]
        )
        if not selected:
            raise RuntimeError("No supported RAGAS metrics selected.")
        if judge_llm_model is None:
            raise RuntimeError("judge_llm_model_id is required for RAGAS evaluation.")
        ragas_llm = _ragas_llm_for_model(judge_llm_model)
        ragas_embeddings = _ragas_embeddings_for_model(embedding_model)
        _bind_ragas_models(selected, llm=ragas_llm, embeddings=ragas_embeddings)
        result = await aevaluate(
            dataset,
            metrics=selected,
            llm=ragas_llm,
            embeddings=ragas_embeddings,
            show_progress=False,
            raise_exceptions=False,
        )
        table = result.to_pandas().to_dict(orient="records")
        item_scores: list[dict[str, float]] = []
        for row in table:
            scores: dict[str, float] = {}
            for key, value in row.items():
                if key not in metric_ids or value is None:
                    continue
                score = float(value)
                if math.isfinite(score):
                    scores[key] = score
            item_scores.append(scores)
        aggregate: dict[str, float] = {}
        for metric_id in metric_ids:
            values = [scores[metric_id] for scores in item_scores if metric_id in scores]
            if values:
                aggregate[metric_id] = round(sum(values) / len(values), 4)
        return aggregate, item_scores


def get_evaluation_adapter(framework_id: str) -> RagasAdapter:
    if framework_id == "ragas":
        return RagasAdapter()
    raise ValueError(f"Unknown evaluation framework: {framework_id}")
