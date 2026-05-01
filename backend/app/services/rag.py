from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.base import ModelClientConfig
from app.clients.factory import create_model_client
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.entities import (
    AgentProfile,
    Chunk,
    ComponentConfig,
    ModelConnection,
    RagFlow,
    RagFlowRun,
    VectorRun,
)
from app.rag.registry import CONFIGURABLE_NODE_TYPES, RagComponentSpec, rag_component_registry
from app.schemas.rag import (
    ComponentConfigCreate,
    ComponentConfigOut,
    ComponentConfigUpdate,
    RagComponentOut,
    RagFlowCreate,
    RagFlowOut,
    RagFlowRunCreate,
    RagFlowRunOut,
    RagFlowRunSummaryOut,
    RagFlowUpdate,
)
from app.observability import create_rag_trace, create_rag_span, create_rag_generation, end_rag_trace
from app.services.vectors import _client_for_model, _collection_config, get_vector_run_model
from app.vectorstores.adapters import get_vectorstore_adapter

logger = logging.getLogger(__name__)


@dataclass
class Passage:
    chunk_id: str
    contents: str
    score: float
    source_file_id: str | None = None
    original_filename: str | None = None
    chunk_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "contents": self.contents,
            "score": self.score,
            "source_file_id": self.source_file_id,
            "original_filename": self.original_filename,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


def _component_out(spec: RagComponentSpec) -> RagComponentOut:
    availability = spec.availability()
    install_hint = f"uv sync --extra {spec.optional_dependency_extra}" if spec.optional_dependency_extra else None
    return RagComponentOut(
        node_type=spec.node_type,
        module_type=spec.module_type,
        display_name=spec.display_name,
        description=spec.description,
        capabilities=list(spec.capabilities),
        config_schema=spec.config_schema,
        secret_config_schema=spec.secret_config_schema,
        default_config=spec.default_config,
        source=spec.source,
        executable=spec.executable,
        requires_config=spec.requires_config,
        required_dependencies=list(spec.required_dependencies),
        required_env_vars=list(spec.required_env_vars),
        requires_llm=spec.requires_llm,
        llm_config_mode=spec.llm_config_mode,
        requires_embedding=spec.requires_embedding,
        requires_api_key=spec.requires_api_key,
        dependency_install_hint=install_hint,
        availability_status=availability.status,
        availability_reason=availability.reason,
    )


async def list_rag_components(node_type: str | None = None) -> list[RagComponentOut]:
    return [_component_out(spec) for spec in rag_component_registry.list(node_type)]


def _encrypt_secret_config(secret_config: dict) -> str | None:
    clean = {key: value for key, value in secret_config.items() if value not in (None, "")}
    if not clean:
        return None
    return encrypt_secret(json.dumps(clean, ensure_ascii=False, sort_keys=True))


def _decrypt_secret_config(value: str | None) -> dict:
    decrypted = decrypt_secret(value)
    if not decrypted:
        return {}
    try:
        parsed = json.loads(decrypted)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _mask_secret_config(value: str | None) -> dict:
    return {key: mask_secret(str(secret_value)) for key, secret_value in _decrypt_secret_config(value).items()}


def _merged_component_config(row: ComponentConfig | None, inline: dict | None = None) -> tuple[dict, bool]:
    config = dict(inline or {})
    has_secret = False
    if row:
        config = dict(row.config or {}) | config
        secret_config = _decrypt_secret_config(row.secret_config_encrypted)
        has_secret = bool(secret_config)
        config = config | secret_config
    return config, has_secret


def _config_out(row: ComponentConfig) -> ComponentConfigOut:
    spec = rag_component_registry.get(row.node_type, row.module_type)
    config, has_secret = _merged_component_config(row)
    availability = spec.availability(config, has_secret) if spec else None
    return ComponentConfigOut.model_validate(row, from_attributes=True).model_copy(
        update={
            "secret_config_masked": _mask_secret_config(row.secret_config_encrypted),
            "availability_status": availability.status if availability else "unknown",
            "availability_reason": availability.reason if availability else "Unknown component.",
        }
    )


async def list_component_configs(session: AsyncSession, node_type: str | None = None) -> list[ComponentConfigOut]:
    stmt = select(ComponentConfig).order_by(ComponentConfig.created_at.desc())
    if node_type:
        stmt = stmt.where(ComponentConfig.node_type == node_type)
    rows = (await session.scalars(stmt)).all()
    return [_config_out(row) for row in rows]


def _validate_component_known(node_type: str, module_type: str) -> RagComponentSpec:
    spec = rag_component_registry.get(node_type, module_type)
    if not spec:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown component: {node_type}/{module_type}")
    return spec


def _validate_config_shape(spec: RagComponentSpec, config: dict, secret_config: dict | None = None) -> None:
    required = spec.config_schema.get("required", [])
    missing = [key for key in required if config.get(key) in (None, "")]
    secret_required = spec.secret_config_schema.get("required", [])
    secret_config = secret_config or {}
    missing_secret = [key for key in secret_required if secret_config.get(key) in (None, "")]
    if missing or missing_secret:
        detail = ", ".join(missing + missing_secret)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing component config: {detail}")


async def create_component_config(session: AsyncSession, payload: ComponentConfigCreate) -> ComponentConfigOut:
    spec = _validate_component_known(payload.node_type, payload.module_type)
    if payload.node_type not in CONFIGURABLE_NODE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only reranker/filter/compressor configs are managed here")
    _validate_config_shape(spec, payload.config, payload.secret_config)
    row = ComponentConfig(
        node_type=payload.node_type,
        module_type=payload.module_type,
        display_name=payload.display_name,
        config=payload.config,
        secret_config_encrypted=_encrypt_secret_config(payload.secret_config),
        enabled=payload.enabled,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _config_out(row)


async def get_component_config(session: AsyncSession, config_id: str) -> ComponentConfig:
    row = await session.get(ComponentConfig, config_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component config not found")
    return row


async def update_component_config(session: AsyncSession, config_id: str, payload: ComponentConfigUpdate) -> ComponentConfigOut:
    row = await get_component_config(session, config_id)
    updates = payload.model_dump(exclude_unset=True)
    secret_config = updates.pop("secret_config", None)
    spec = _validate_component_known(row.node_type, row.module_type)
    next_config = updates.get("config", row.config or {})
    if secret_config is not None:
        next_secret = secret_config
    else:
        next_secret = _decrypt_secret_config(row.secret_config_encrypted)
    _validate_config_shape(spec, next_config, next_secret)
    for key, value in updates.items():
        setattr(row, key, value)
    if secret_config is not None:
        row.secret_config_encrypted = _encrypt_secret_config(secret_config)
    await session.commit()
    await session.refresh(row)
    return _config_out(row)


async def delete_component_config(session: AsyncSession, config_id: str) -> None:
    row = await get_component_config(session, config_id)
    await session.delete(row)
    await session.commit()


def _flow_out(flow: RagFlow) -> RagFlowOut:
    vector = flow.vector_run
    return RagFlowOut.model_validate(flow, from_attributes=True).model_copy(
        update={
            "vector_run_status": vector.status if vector else None,
            "batch_name": vector.batch.batch_name if vector and vector.batch else None,
            "vectordb_name": vector.vectordb_name if vector else None,
        }
    )


async def _validate_flow_payload(
    session: AsyncSession,
    *,
    vector_run_id: str,
    nodes: list[dict],
) -> VectorRun:
    vector_run = await get_vector_run_model(session, vector_run_id)
    if vector_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vector run is not completed")
    retrieval_nodes = [node for node in nodes if node.get("enabled", True) and node.get("node_type") == "retrieval"]
    if len(retrieval_nodes) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RAG flow requires exactly one enabled retrieval node. Call get_rag_flow_build_guide and list_rag_components, then include one retrieval node such as module_type='vectordb'.",
        )
    generator_nodes = [node for node in nodes if node.get("enabled", True) and node.get("node_type") == "answer_generator"]
    if len(generator_nodes) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "RAG flow requires exactly one enabled answer_generator node, usually as the final node. "
                "Use module_type='llm_answer' and config.agent_id from list_agent_profiles; do not use raw model_id for agent_profile_required nodes."
            ),
        )
    for node in nodes:
        if not node.get("enabled", True):
            continue
        node_type = node["node_type"]
        module_type = node["module_type"]
        spec = _validate_component_known(node_type, module_type)
        config_id = node.get("component_config_id")
        component = None
        if config_id:
            component = await get_component_config(session, config_id)
            if component.node_type != node_type or component.module_type != module_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Component config does not match node. component_config_id is only for reusable "
                        "passage_reranker, passage_filter or passage_compressor configs with the same node_type/module_type."
                    ),
                )
            if not component.enabled:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Component config is disabled")
        config, has_secret = _merged_component_config(component, node.get("config") or {})
        if spec.llm_config_mode == "agent_profile_required" and config.get("model_id") and not config.get("agent_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{node_type}/{module_type} requires config.agent_id from an Agent Profile, not raw model_id. "
                    "Call list_agent_profiles or create_agent_profile, then pass config={'agent_id': '<agent_id>'}."
                ),
            )
        availability = spec.availability(config, has_secret)
        if availability.status != "available":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{module_type} is not executable: {availability.reason}. Call get_rag_flow_build_guide, list_rag_components and list_agent_profiles to choose valid config.",
            )
    return vector_run


async def create_rag_flow(session: AsyncSession, payload: RagFlowCreate) -> RagFlowOut:
    nodes = [node.model_dump() for node in payload.nodes]
    await _validate_flow_payload(session, vector_run_id=payload.vector_run_id, nodes=nodes)
    flow = RagFlow(
        flow_name=payload.flow_name,
        description=payload.description,
        vector_run_id=payload.vector_run_id,
        retrieval_config=payload.retrieval_config,
        nodes=nodes,
        enabled=payload.enabled,
    )
    session.add(flow)
    await session.commit()
    return _flow_out(await get_rag_flow_model(session, flow.flow_id))


async def get_rag_flow_model(session: AsyncSession, flow_id: str) -> RagFlow:
    flow = await session.scalar(
        select(RagFlow)
        .where(RagFlow.flow_id == flow_id)
        .options(selectinload(RagFlow.vector_run).selectinload(VectorRun.batch))
    )
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG flow not found")
    return flow


async def list_rag_flows(session: AsyncSession) -> list[RagFlowOut]:
    flows = (
        await session.scalars(
            select(RagFlow)
            .options(selectinload(RagFlow.vector_run).selectinload(VectorRun.batch))
            .order_by(RagFlow.created_at.desc())
        )
    ).all()
    return [_flow_out(flow) for flow in flows]


async def get_rag_flow(session: AsyncSession, flow_id: str) -> RagFlowOut:
    return _flow_out(await get_rag_flow_model(session, flow_id))


async def update_rag_flow(session: AsyncSession, flow_id: str, payload: RagFlowUpdate) -> RagFlowOut:
    flow = await get_rag_flow_model(session, flow_id)
    updates = payload.model_dump(exclude_unset=True)
    if "nodes" in updates:
        updates["nodes"] = [node.model_dump() if hasattr(node, "model_dump") else node for node in updates["nodes"]]
    vector_run_id = updates.get("vector_run_id", flow.vector_run_id)
    nodes = updates.get("nodes", flow.nodes)
    if "vector_run_id" in updates or "nodes" in updates:
        await _validate_flow_payload(session, vector_run_id=vector_run_id, nodes=nodes)
    for key, value in updates.items():
        setattr(flow, key, value)
    await session.commit()
    return _flow_out(await get_rag_flow_model(session, flow_id))


async def delete_rag_flow(session: AsyncSession, flow_id: str) -> None:
    flow = await get_rag_flow_model(session, flow_id)
    await session.delete(flow)
    await session.commit()


def _trace(
    *,
    node_type: str,
    module_type: str,
    started: float,
    activated: bool,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    status_value: str = "success",
    error: str | None = None,
) -> dict:
    return {
        "node_type": node_type,
        "module_type": module_type,
        "status": status_value,
        "activated": activated,
        "input_summary": input_summary or {},
        "output_summary": output_summary or {},
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
    }


def _passage_summary(passages: list[Passage]) -> dict:
    return {
        "passage_count": len(passages),
        "chunk_ids": [passage.chunk_id for passage in passages[:10]],
    }


def _passage_preview(passages: list[Passage], limit: int = 3, content_chars: int = 180) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for passage in passages[: max(limit, 0)]:
        previews.append(
            {
                "chunk_id": passage.chunk_id,
                "score": round(float(passage.score), 6),
                "original_filename": passage.original_filename,
                "contents_preview": (passage.contents or "")[: max(content_chars, 0)],
            }
        )
    return previews


def _error_text(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


async def _run_prompt(
    session: AsyncSession,
    *,
    config: dict,
    prompt: str,
    query: str,
    langfuse_parent: Any = None,
    generation_name: str = "llm_call",
) -> str:
    agent_id = config.get("agent_id")
    if agent_id:
        agent = await session.get(AgentProfile, agent_id)
        if not agent or not agent.enabled:
            raise ValueError("Agent Profile is unavailable")
        model = await session.get(ModelConnection, agent.model_id)
        if not model:
            raise ValueError("Agent model is unavailable")
        rendered = _render_agent_prompt(agent.prompt_template, prompt, query)
        runtime = dict(agent.runtime_config or {}) | config
    else:
        model_id = config.get("model_id")
        if not model_id:
            raise ValueError("model_id or agent_id is required")
        model = await session.get(ModelConnection, model_id)
        if not model or not model.enabled:
            raise ValueError("LLM model is unavailable")
        rendered = prompt
        runtime = config
    client = create_model_client(
        ModelClientConfig(
            provider=model.provider,
            base_url=model.base_url,
            model_name=model.model_name,
            model_category=model.model_category,
            api_key=decrypt_secret(model.api_key_encrypted),
            timeout_seconds=model.timeout_seconds,
            max_retries=model.max_retries,
        )
    )
    gen = create_rag_generation(
        langfuse_parent,
        name=generation_name,
        model=model.model_name,
        input=rendered[:4000],
    )
    result = await client.chat(
        rendered,
        temperature=float(runtime.get("temperature", 0)),
        max_tokens=runtime.get("max_output_tokens"),
    )
    if gen:
        try:
            gen.end(output=result.text[:2000] if result.text else "")
        except Exception:
            pass
    return result.text or ""


def _render_agent_prompt(template: str, prompt: str, query: str) -> str:
    return f"{template.strip()}\n\n用户原始提问：\n{query}\n\n当前节点输入：\n{prompt}"


def _split_queries(text: str, fallback: str) -> list[str]:
    candidates = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            candidates = [str(item) for item in parsed]
        elif isinstance(parsed, dict):
            for key in ["queries", "semantic_queries", "query", "hypothetical_document"]:
                value = parsed.get(key)
                if isinstance(value, list):
                    candidates.extend(str(item) for item in value)
                elif isinstance(value, str):
                    candidates.append(value)
    except json.JSONDecodeError:
        candidates = [re.sub(r"^\s*[-*\d.]+\s*", "", line).strip() for line in text.splitlines()]
    clean = [item for item in candidates if item]
    return clean or [fallback]


async def _query_expansion(
    session: AsyncSession,
    query: str,
    node: dict,
    config: dict,
    langfuse_parent: Any = None,
) -> tuple[list[str], dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    if module_type == "pass_query_expansion":
        return [query], _trace(
            node_type="query_expansion",
            module_type=module_type,
            started=started,
            activated=False,
            input_summary={"query": query},
            output_summary=_query_expansion_summary(query, [query], ""),
        )
    prompts = {
        "query_decompose": "Break the query into focused retrieval queries. Return one query per line.\n\nQuery: {query}",
        "hyde": "Write a concise hypothetical document that would answer this query for retrieval.\n\nQuery: {query}",
        "multi_query_expansion": "Generate diverse retrieval queries. Return one query per line.\n\nQuery: {query}",
    }
    span = create_rag_span(langfuse_parent, name=f"query_expansion:{module_type}", input=query)
    output = await _run_prompt(
        session,
        config=config,
        prompt=prompts.get(module_type, "{query}").format(query=query),
        query=query,
        langfuse_parent=span or langfuse_parent,
        generation_name=f"query_expansion:{module_type}",
    )
    expanded = _split_queries(output, query)
    if query not in expanded:
        expanded = [query] + expanded
    if span:
        try:
            span.end(output={"expanded_queries": expanded})
        except Exception:
            pass
    return expanded, _trace(
        node_type="query_expansion",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary={"query": query},
        output_summary=_query_expansion_summary(query, expanded, output),
    )


def _query_expansion_summary(query: str, expanded: list[str], raw_output: str) -> dict:
    expanded_queries = [item for item in expanded if item != query]
    return {
        "original_query": query,
        "expanded_queries": expanded_queries,
        "raw_output": raw_output[:1200],
    }


def _tokenize_bm25(text: str, tokenizer: str = "simple") -> list[str]:
    if tokenizer == "space":
        return [item for item in text.lower().split() if item]
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


def _bm25_scores(query_tokens: list[str], documents: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    if not documents or not query_tokens:
        return [0.0 for _ in documents]
    doc_count = len(documents)
    avgdl = sum(len(document) for document in documents) / max(doc_count, 1)
    dfs: Counter[str] = Counter()
    counters = [Counter(document) for document in documents]
    for counter in counters:
        dfs.update(counter.keys())
    scores: list[float] = []
    for document, counter in zip(documents, counters, strict=True):
        doc_len = len(document) or 1
        score = 0.0
        for token in query_tokens:
            tf = counter.get(token, 0)
            if not tf:
                continue
            df = dfs[token]
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * doc_len / max(avgdl, 1))
            score += idf * (tf * (k1 + 1) / denominator)
        scores.append(score)
    return scores


def _copy_passage(passage: Passage, *, score: float | None = None, metadata: dict | None = None) -> Passage:
    return Passage(
        chunk_id=passage.chunk_id,
        contents=passage.contents,
        score=passage.score if score is None else score,
        source_file_id=passage.source_file_id,
        original_filename=passage.original_filename,
        chunk_index=passage.chunk_index,
        metadata=dict(passage.metadata or {}) | dict(metadata or {}),
    )


def _annotate_retrieval_passage(
    passage: Passage,
    *,
    module_type: str,
    source: str,
    query: str,
    score: float,
    rank: int,
) -> Passage:
    return _copy_passage(
        passage,
        score=score,
        metadata={
            "retrieval_module": module_type,
            "matched_queries": [query],
            "source_scores": {source: score},
            "fusion_score": score,
            "retrieval_sources": [source],
            "retrieval_rank": rank,
        },
    )


def _merge_by_max_score(lists: list[list[Passage]], *, module_type: str, top_k: int) -> list[Passage]:
    merged: dict[str, Passage] = {}
    for passages in lists:
        for passage in passages:
            current = merged.get(passage.chunk_id)
            if not current or passage.score > current.score:
                base = passage
            else:
                base = current
            metadata = dict(base.metadata or {})
            matched_queries = list(dict.fromkeys((current.metadata.get("matched_queries", []) if current else []) + passage.metadata.get("matched_queries", [])))
            retrieval_sources = list(dict.fromkeys((current.metadata.get("retrieval_sources", []) if current else []) + passage.metadata.get("retrieval_sources", [])))
            source_scores = dict(current.metadata.get("source_scores", {}) if current else {})
            for source, score in passage.metadata.get("source_scores", {}).items():
                source_scores[source] = max(float(source_scores.get(source, float("-inf"))), float(score))
            metadata.update(
                {
                    "retrieval_module": module_type,
                    "matched_queries": matched_queries,
                    "source_scores": source_scores,
                    "fusion_score": base.score,
                    "retrieval_sources": retrieval_sources,
                }
            )
            merged[passage.chunk_id] = _copy_passage(base, metadata=metadata)
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:top_k]


async def _hydrate_passages(session: AsyncSession, passages: list[Passage]) -> list[Passage]:
    by_chunk = {passage.chunk_id: passage for passage in passages}
    if not by_chunk:
        return passages
    chunks = (
        await session.scalars(
            select(Chunk)
            .where(Chunk.chunk_id.in_(list(by_chunk)))
            .options(selectinload(Chunk.source_file))
        )
    ).all()
    for chunk in chunks:
        passage = by_chunk.get(chunk.chunk_id)
        if passage:
            passage.contents = passage.contents or chunk.contents
            passage.source_file_id = chunk.source_file_id
            passage.original_filename = chunk.source_file.original_filename if chunk.source_file else passage.original_filename
            passage.chunk_index = chunk.chunk_index
    return passages


async def _semantic_ranked_lists(session: AsyncSession, vector_run: VectorRun, queries: list[str], top_k: int, module_type: str = "vectordb") -> list[list[Passage]]:
    model = await session.get(ModelConnection, vector_run.embedding_model_id)
    if not model:
        raise ValueError("Embedding model is unavailable")
    client = _client_for_model(model)
    adapter = get_vectorstore_adapter(vector_run.vectordb_name)
    config = _collection_config(vector_run, vector_run.embedding_dimension or 0)
    ranked_lists: list[list[Passage]] = []
    for query in queries:
        embedding_result = await client.embedding(query)
        embedding = [float(value) for value in (embedding_result.data or [])]
        if vector_run.embedding_config.get("normalize_embeddings"):
            norm = sum(value * value for value in embedding) ** 0.5
            if norm:
                embedding = [value / norm for value in embedding]
        rows: list[Passage] = []
        for rank, result in enumerate(await adapter.search_vectors(config, embedding, top_k), start=1):
            chunk_id = result.metadata.get("chunk_id") or result.vector_id
            rows.append(
                _annotate_retrieval_passage(
                    Passage(
                        chunk_id=str(chunk_id),
                        contents=result.text,
                        score=float(result.score),
                        source_file_id=result.metadata.get("source_file_id"),
                        original_filename=result.metadata.get("original_filename"),
                        chunk_index=result.metadata.get("chunk_index"),
                        metadata=result.metadata,
                    ),
                    module_type=module_type,
                    source="semantic",
                    query=query,
                    score=float(result.score),
                    rank=rank,
                )
            )
        ranked_lists.append(await _hydrate_passages(session, rows))
    return ranked_lists


async def _bm25_ranked_lists(session: AsyncSession, vector_run: VectorRun, queries: list[str], top_k: int, config: dict, module_type: str = "bm25") -> list[list[Passage]]:
    tokenizer = str(config.get("bm25_tokenizer") or "simple")
    chunks = (
        await session.scalars(
            select(Chunk)
            .where(Chunk.run_id == vector_run.chunk_run_id)
            .options(selectinload(Chunk.source_file))
            .order_by(Chunk.chunk_index)
        )
    ).all()
    documents = [_tokenize_bm25(chunk.contents, tokenizer) for chunk in chunks]
    ranked_lists: list[list[Passage]] = []
    for query in queries:
        scores = _bm25_scores(_tokenize_bm25(query, tokenizer), documents)
        ranked_indexes = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
        rows: list[Passage] = []
        for rank, index in enumerate(ranked_indexes, start=1):
            score = float(scores[index])
            if score <= 0:
                continue
            chunk = chunks[index]
            rows.append(
                _annotate_retrieval_passage(
                    Passage(
                        chunk_id=chunk.chunk_id,
                        contents=chunk.contents,
                        score=score,
                        source_file_id=chunk.source_file_id,
                        original_filename=chunk.source_file.original_filename if chunk.source_file else None,
                        chunk_index=chunk.chunk_index,
                        metadata=dict(chunk.chunk_metadata or {}),
                    ),
                    module_type=module_type,
                    source="lexical",
                    query=query,
                    score=score,
                    rank=rank,
                )
            )
        ranked_lists.append(rows)
    return ranked_lists


def _flatten_ranked_lists(lists: list[list[Passage]]) -> list[Passage]:
    return [passage for passages in lists for passage in passages]


def _normalize_scores(scores: list[float], method: str, *, theoretical_min: float = 0.0) -> list[float]:
    if not scores:
        return []
    if len(set(scores)) == 1:
        return [1.0 for _ in scores]
    if method == "z":
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        std = variance**0.5
        zscores = [(score - mean) / std for score in scores] if std else [0.0 for _ in scores]
        return _normalize_scores(zscores, "mm")
    if method == "dbsf":
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        std = variance**0.5
        if not std:
            return [1.0 for _ in scores]
        return [min(max((score - (mean - 3 * std)) / (6 * std), 0.0), 1.0) for score in scores]
    min_score = theoretical_min if method == "tmm" else min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [1.0 for _ in scores]
    return [min(max((score - min_score) / (max_score - min_score), 0.0), 1.0) for score in scores]


def _hybrid_rrf(lexical_lists: list[list[Passage]], semantic_lists: list[list[Passage]], config: dict, top_k: int) -> list[Passage]:
    rrf_k = float(config.get("rrf_k") or 60)
    weights = {"lexical": float(config.get("lexical_weight") or 1.0), "semantic": float(config.get("semantic_weight") or 1.0)}
    scores: dict[str, float] = defaultdict(float)
    passages: dict[str, Passage] = {}
    matched_queries: dict[str, list[str]] = defaultdict(list)
    source_scores: dict[str, dict[str, float]] = defaultdict(dict)
    for source, ranked_lists in [("lexical", lexical_lists), ("semantic", semantic_lists)]:
        for ranked in ranked_lists:
            for rank, passage in enumerate(ranked, start=1):
                scores[passage.chunk_id] += weights[source] / (rrf_k + rank)
                passages.setdefault(passage.chunk_id, passage)
                matched_queries[passage.chunk_id].extend(passage.metadata.get("matched_queries", []))
                source_scores[passage.chunk_id][source] = max(float(source_scores[passage.chunk_id].get(source, 0)), float(passage.score))
    output = []
    for chunk_id, score in scores.items():
        sources = list(source_scores[chunk_id])
        output.append(
            _copy_passage(
                passages[chunk_id],
                score=score,
                metadata={
                    "retrieval_module": "hybrid_rrf",
                    "matched_queries": list(dict.fromkeys(matched_queries[chunk_id])),
                    "source_scores": source_scores[chunk_id],
                    "fusion_score": score,
                    "retrieval_sources": sources,
                },
            )
        )
    return sorted(output, key=lambda item: item.score, reverse=True)[:top_k]


def _hybrid_cc(lexical_lists: list[list[Passage]], semantic_lists: list[list[Passage]], config: dict, top_k: int) -> list[Passage]:
    method = str(config.get("normalize_method") or "mm")
    weights = {"lexical": float(config.get("lexical_weight") or 0.5), "semantic": float(config.get("semantic_weight") or 0.5)}
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"lexical": [], "semantic": []})
    raw_scores: dict[str, dict[str, float]] = defaultdict(dict)
    passages: dict[str, Passage] = {}
    matched_queries: dict[str, list[str]] = defaultdict(list)
    for source, ranked_lists in [("lexical", lexical_lists), ("semantic", semantic_lists)]:
        theoretical_min = float(config.get(f"{source}_theoretical_min_value", 0 if source == "lexical" else -1))
        for ranked in ranked_lists:
            normalized = _normalize_scores([passage.score for passage in ranked], method, theoretical_min=theoretical_min)
            for passage, score in zip(ranked, normalized, strict=True):
                values[passage.chunk_id][source].append(score)
                raw_scores[passage.chunk_id][source] = max(float(raw_scores[passage.chunk_id].get(source, 0)), float(passage.score))
                passages.setdefault(passage.chunk_id, passage)
                matched_queries[passage.chunk_id].extend(passage.metadata.get("matched_queries", []))
    output = []
    for chunk_id, source_values in values.items():
        lexical_score = sum(source_values["lexical"]) / len(source_values["lexical"]) if source_values["lexical"] else 0.0
        semantic_score = sum(source_values["semantic"]) / len(source_values["semantic"]) if source_values["semantic"] else 0.0
        fusion_score = weights["lexical"] * lexical_score + weights["semantic"] * semantic_score
        sources = [source for source, items in source_values.items() if items]
        output.append(
            _copy_passage(
                passages[chunk_id],
                score=fusion_score,
                metadata={
                    "retrieval_module": "hybrid_cc",
                    "matched_queries": list(dict.fromkeys(matched_queries[chunk_id])),
                    "source_scores": raw_scores[chunk_id] | {"lexical_normalized": lexical_score, "semantic_normalized": semantic_score},
                    "fusion_score": fusion_score,
                    "retrieval_sources": sources,
                },
            )
        )
    return sorted(output, key=lambda item: item.score, reverse=True)[:top_k]


def _retrieval_candidate_top_ks(module_type: str, config: dict, final_top_k: int) -> tuple[int, int]:
    if module_type not in {"hybrid_rrf", "hybrid_cc"}:
        return final_top_k, final_top_k
    lexical_top_k = int(config.get("bm25_top_k") or final_top_k)
    semantic_top_k = int(config.get("vectordb_top_k") or final_top_k)
    return max(lexical_top_k, 1), max(semantic_top_k, 1)


async def _retrieve(session: AsyncSession, vector_run: VectorRun, queries: list[str], node: dict) -> tuple[list[Passage], dict]:
    started = time.perf_counter()
    module_type = node.get("module_type", "vectordb")
    config = dict(node.get("config") or {})
    top_k = int(config.get("top_k") or 5)
    lexical_top_k, semantic_top_k = _retrieval_candidate_top_ks(module_type, config, top_k)
    lexical_lists: list[list[Passage]] = []
    semantic_lists: list[list[Passage]] = []
    if module_type in {"bm25", "hybrid_rrf", "hybrid_cc"}:
        lexical_lists = await _bm25_ranked_lists(session, vector_run, queries, lexical_top_k, config, module_type=module_type)
    if module_type in {"vectordb", "hybrid_rrf", "hybrid_cc"}:
        semantic_lists = await _semantic_ranked_lists(session, vector_run, queries, semantic_top_k, module_type=module_type)
    if module_type == "bm25":
        passages = _merge_by_max_score(lexical_lists, module_type=module_type, top_k=top_k)
    elif module_type == "vectordb":
        passages = _merge_by_max_score(semantic_lists, module_type=module_type, top_k=top_k)
    elif module_type == "hybrid_rrf":
        passages = _hybrid_rrf(lexical_lists, semantic_lists, config, top_k)
    elif module_type == "hybrid_cc":
        passages = _hybrid_cc(lexical_lists, semantic_lists, config, top_k)
    else:
        raise ValueError(f"Unsupported retrieval module: {module_type}")
    return passages, _trace(
        node_type="retrieval",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary={
            "query_count": len(queries),
            "top_k": top_k,
            "bm25_top_k": lexical_top_k if module_type in {"bm25", "hybrid_rrf", "hybrid_cc"} else None,
            "vectordb_top_k": semantic_top_k if module_type in {"vectordb", "hybrid_rrf", "hybrid_cc"} else None,
            "retrieval_module": module_type,
        },
        output_summary=_passage_summary(passages)
        | {
            "retrieval_module": module_type,
            "lexical_candidate_count": len(_flatten_ranked_lists(lexical_lists)),
            "semantic_candidate_count": len(_flatten_ranked_lists(semantic_lists)),
            "candidate_top_k": {
                "bm25_top_k": lexical_top_k if module_type in {"bm25", "hybrid_rrf", "hybrid_cc"} else None,
                "vectordb_top_k": semantic_top_k if module_type in {"vectordb", "hybrid_rrf", "hybrid_cc"} else None,
                "final_top_k": top_k,
            },
            "fusion_weights": {
                "lexical_weight": config.get("lexical_weight"),
                "semantic_weight": config.get("semantic_weight"),
                "rrf_k": config.get("rrf_k"),
                "normalize_method": config.get("normalize_method"),
            },
        },
    )


async def _augment(session: AsyncSession, vector_run: VectorRun, passages: list[Passage], node: dict, config: dict) -> tuple[list[Passage], dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    if module_type == "pass_passage_augmenter":
        return passages, _trace(node_type="passage_augmenter", module_type=module_type, started=started, activated=False, input_summary=_passage_summary(passages), output_summary=_passage_summary(passages))
    previous = int(config.get("previous_chunks", 0) or 0)
    next_count = int(config.get("next_chunks", 0) or 0)
    top_k = int(config.get("top_k") or len(passages))
    targets = passages[: max(top_k, 1)]
    output: dict[str, Passage] = {passage.chunk_id: passage for passage in passages}
    for passage in targets:
        if passage.source_file_id is None or passage.chunk_index is None:
            continue
        min_index = max(int(passage.chunk_index) - previous, 0)
        max_index = int(passage.chunk_index) + next_count
        rows = (
            await session.scalars(
                select(Chunk)
                .where(
                    Chunk.run_id == vector_run.chunk_run_id,
                    Chunk.source_file_id == passage.source_file_id,
                    Chunk.chunk_index >= min_index,
                    Chunk.chunk_index <= max_index,
                )
                .options(selectinload(Chunk.source_file))
                .order_by(Chunk.chunk_index)
            )
        ).all()
        for chunk in rows:
            output.setdefault(
                chunk.chunk_id,
                Passage(
                    chunk_id=chunk.chunk_id,
                    contents=chunk.contents,
                    score=passage.score * 0.95,
                    source_file_id=chunk.source_file_id,
                    original_filename=chunk.source_file.original_filename if chunk.source_file else None,
                    chunk_index=chunk.chunk_index,
                    metadata={"augmented_from": passage.chunk_id, "chunk_index": chunk.chunk_index},
                ),
            )
    augmented = sorted(output.values(), key=lambda item: (item.score, -(item.chunk_index or 0)), reverse=True)
    return augmented, _trace(
        node_type="passage_augmenter",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary=_passage_summary(passages),
        output_summary=_passage_summary(augmented),
    )


async def _api_rerank(module_type: str, query: str, passages: list[Passage], config: dict) -> list[Passage]:
    api_key = config.get("api_key")
    top_k = int(config.get("top_k") or len(passages))
    documents = [passage.contents for passage in passages]
    timeout = float(config.get("timeout_seconds", 30))
    async with httpx.AsyncClient(timeout=timeout) as client:
        if module_type == "cohere_reranker":
            response = await client.post(
                "https://api.cohere.com/v2/rerank",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": config.get("model", "rerank-v3.5"), "query": query, "documents": documents, "top_n": top_k},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            return [passages[item["index"]] for item in results if item.get("index") is not None]
        if module_type == "voyageai_reranker":
            response = await client.post(
                "https://api.voyageai.com/v1/rerank",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": config.get("model", "rerank-2"), "query": query, "documents": documents, "top_k": top_k},
            )
            response.raise_for_status()
            results = response.json().get("data", [])
            return [passages[item["index"]] for item in results if item.get("index") is not None]
        endpoint = "https://api.jina.ai/v1/rerank" if module_type == "jina_reranker" else "https://api.mixedbread.ai/v1/reranking"
        response = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": config.get("model"), "query": query, "documents": documents, "top_n": top_k},
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return [passages[item["index"]] for item in results if item.get("index") is not None]


async def _rerank(session: AsyncSession, query: str, passages: list[Passage], node: dict, config: dict, langfuse_parent: Any = None) -> tuple[list[Passage], dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    top_k = int(config.get("top_k") or len(passages))
    if module_type == "pass_reranker":
        output = passages[:top_k]
        return output, _trace(node_type="passage_reranker", module_type=module_type, started=started, activated=False, input_summary=_passage_summary(passages), output_summary=_passage_summary(output))
    if module_type == "time_reranker":
        output = sorted(passages, key=lambda item: str(item.metadata.get("last_modified_datetime", "")), reverse=True)[:top_k]
    elif module_type == "rankgpt":
        prompt = "Rank these passages for the query. Return chunk ids in best order.\nQuery: {query}\n\n{passages}".format(
            query=query,
            passages="\n\n".join(f"{item.chunk_id}: {item.contents[:700]}" for item in passages),
        )
        ranked_text = await _run_prompt(session, config=config, prompt=prompt, query=query, langfuse_parent=langfuse_parent, generation_name="reranker:rankgpt")
        ids = re.findall(r"[0-9a-fA-F-]{32,36}", ranked_text)
        by_id = {item.chunk_id: item for item in passages}
        ranked = [by_id[item] for item in ids if item in by_id]
        output = (ranked + [item for item in passages if item.chunk_id not in set(ids)])[:top_k]
    elif module_type in {"cohere_reranker", "voyageai_reranker", "jina_reranker", "mixedbread_ai_reranker"}:
        output = await _api_rerank(module_type, query, passages, config)
        output = output[:top_k]
    else:
        raise ValueError(f"{module_type} is registered but not executable in this runtime")
    return output, _trace(
        node_type="passage_reranker",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary=_passage_summary(passages),
        output_summary=_passage_summary(output),
    )


def _filter(passages: list[Passage], node: dict, config: dict) -> tuple[list[Passage], dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    if module_type == "pass_passage_filter":
        return passages, _trace(node_type="passage_filter", module_type=module_type, started=started, activated=False, input_summary=_passage_summary(passages), output_summary=_passage_summary(passages))
    if module_type in {"similarity_threshold_cutoff", "threshold_cutoff"}:
        threshold = float(config.get("threshold", 0.5))
        output = [passage for passage in passages if passage.score >= threshold]
    elif module_type in {"similarity_percentile_cutoff", "percentile_cutoff"}:
        percentile = float(config.get("percentile", 50))
        scores = sorted(passage.score for passage in passages)
        if not scores:
            output = []
        else:
            index = min(max(int((percentile / 100) * (len(scores) - 1)), 0), len(scores) - 1)
            cutoff = scores[index]
            output = [passage for passage in passages if passage.score >= cutoff]
    elif module_type == "recency_filter":
        threshold = str(config.get("threshold_datetime") or "")
        field = str(config.get("metadata_field") or "last_modified_datetime")
        output = [passage for passage in passages if str(passage.metadata.get(field, "")) >= threshold]
        if not output and passages:
            output = [max(passages, key=lambda item: str(item.metadata.get(field, "")))]
    else:
        output = passages
    return output, _trace(
        node_type="passage_filter",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary=_passage_summary(passages),
        output_summary=_passage_summary(output),
    )


async def _compress(session: AsyncSession, query: str, passages: list[Passage], node: dict, config: dict, langfuse_parent: Any = None) -> tuple[list[Passage], dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    if module_type == "pass_compressor":
        return passages, _trace(node_type="passage_compressor", module_type=module_type, started=started, activated=False, input_summary=_passage_summary(passages), output_summary=_passage_summary(passages))
    if module_type not in {"tree_summarize", "refine"}:
        raise ValueError(f"{module_type} is registered but not executable in this runtime")
    compressed: list[Passage] = []
    target_chars = int(config.get("target_chars") or 700)
    for passage in passages:
        prompt = (
            "Compress the passage for RAG context. Preserve facts useful for the query.\n"
            f"Query: {query}\n\nPassage:\n{passage.contents[:4000]}"
        )
        text = await _run_prompt(session, config=config, prompt=prompt, query=query, langfuse_parent=langfuse_parent, generation_name=f"compressor:{module_type}")
        compressed.append(
            Passage(
                chunk_id=passage.chunk_id,
                contents=(text or passage.contents)[:target_chars],
                score=passage.score,
                source_file_id=passage.source_file_id,
                original_filename=passage.original_filename,
                chunk_index=passage.chunk_index,
                metadata=passage.metadata | {"compressed_by": module_type},
            )
        )
    return compressed, _trace(
        node_type="passage_compressor",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary=_passage_summary(passages),
        output_summary=_passage_summary(compressed),
    )


async def _answer(
    session: AsyncSession,
    query: str,
    passages: list[Passage],
    node: dict,
    config: dict,
    langfuse_parent: Any = None,
) -> tuple[str, dict, dict]:
    started = time.perf_counter()
    module_type = node["module_type"]
    if module_type != "llm_answer":
        raise ValueError(f"{module_type} is registered but not executable in this runtime")
    context = "\n\n".join(
        f"[{index + 1}] {passage.contents[:4000]}"
        for index, passage in enumerate(passages)
    )
    system_prompt = str(
        config.get("system_prompt")
        or "请仅基于给定上下文回答问题。若上下文不足，请明确说明无法从材料中确定。"
    )
    prompt = (
        f"{system_prompt}\n\n"
        f"问题：\n{query}\n\n"
        f"上下文：\n{context or '无可用上下文'}\n\n"
        "请输出最终答案。"
    )
    answer = await _run_prompt(session, config=config, prompt=prompt, query=query, langfuse_parent=langfuse_parent, generation_name="answer_generator:llm_answer")
    metadata = {
        "context_count": len(passages),
        "source_chunk_ids": [passage.chunk_id for passage in passages],
        "model_id": config.get("model_id"),
        "agent_id": config.get("agent_id"),
    }
    return answer, metadata, _trace(
        node_type="answer_generator",
        module_type=module_type,
        started=started,
        activated=True,
        input_summary={"query": query, "context_count": len(passages)},
        output_summary={"answer_chars": len(answer), "source_chunk_ids": metadata["source_chunk_ids"][:10]},
    )


async def _node_config(session: AsyncSession, node: dict) -> tuple[RagComponentSpec, dict, bool]:
    spec = _validate_component_known(node["node_type"], node["module_type"])
    component = await get_component_config(session, node["component_config_id"]) if node.get("component_config_id") else None
    if component and not component.enabled:
        raise ValueError("Component config is disabled")
    config, has_secret = _merged_component_config(component, node.get("config") or {})
    availability = spec.availability(config, has_secret)
    if availability.status != "available":
        raise ValueError(f"{node['module_type']} is not executable: {availability.reason}")
    return spec, config, has_secret


def _retrieval_node(flow: RagFlow) -> dict:
    for node in flow.nodes or []:
        if node.get("enabled", True) and node.get("node_type") == "retrieval":
            return node
    return {
        "node_type": "retrieval",
        "module_type": "vectordb",
        "config": {"top_k": int((flow.retrieval_config or {}).get("top_k") or 5)},
        "enabled": True,
    }


async def run_rag_flow(session: AsyncSession, flow_id: str, payload: RagFlowRunCreate) -> RagFlowRunOut:
    flow = await get_rag_flow_model(session, flow_id)
    if not flow.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RAG flow is disabled")
    vector_run = await get_vector_run_model(session, flow.vector_run_id)
    run = RagFlowRun(flow_id=flow.flow_id, query=payload.query, status="running")
    session.add(run)
    await session.commit()
    started = time.perf_counter()
    trace_events: list[dict] = []
    lf_ctx = create_rag_trace(
        name=f"rag_flow:{flow.flow_name}",
        session_id=flow.flow_id,
        metadata={"flow_id": flow.flow_id, "flow_name": flow.flow_name, "run_id": run.run_id},
        input=payload.query,
        tags=["rag_flow"],
    )
    try:
        query = payload.query
        queries = [query]
        for node in [item for item in flow.nodes if item.get("enabled", True) and item.get("node_type") == "query_expansion"]:
            _, config, _ = await _node_config(session, node)
            queries, event = await _query_expansion(session, query, node, config, langfuse_parent=lf_ctx.trace)
            trace_events.append(event)
        retrieval_node = _retrieval_node(flow)
        _, retrieval_config, _ = await _node_config(session, retrieval_node)
        retrieval_node = dict(retrieval_node) | {"config": retrieval_config}
        retrieval_span = create_rag_span(lf_ctx.trace, name=f"retrieval:{retrieval_node.get('module_type', 'vectordb')}", input={"queries": queries})
        passages, event = await _retrieve(session, vector_run, queries, retrieval_node)
        if retrieval_span:
            try:
                retrieval_span.end(
                    output={
                        "passage_count": len(passages),
                        "chunk_ids": [passage.chunk_id for passage in passages[:10]],
                        "top_passages": _passage_preview(passages),
                    }
                )
            except Exception:
                pass
        trace_events.append(event)
        for node in [item for item in flow.nodes if item.get("enabled", True) and item.get("node_type") not in {"query_expansion", "retrieval", "answer_generator"}]:
            _, config, _ = await _node_config(session, node)
            node_type = node["node_type"]
            if node_type == "passage_augmenter":
                passages, event = await _augment(session, vector_run, passages, node, config)
            elif node_type == "passage_reranker":
                passages, event = await _rerank(session, query, passages, node, config, langfuse_parent=lf_ctx.trace)
            elif node_type == "passage_filter":
                passages, event = _filter(passages, node, config)
            elif node_type == "passage_compressor":
                passages, event = await _compress(session, query, passages, node, config, langfuse_parent=lf_ctx.trace)
            else:
                raise ValueError(f"Unsupported node type: {node_type}")
            trace_events.append(event)
        answer_nodes = [
            item
            for item in flow.nodes
            if item.get("enabled", True) and item.get("node_type") == "answer_generator"
        ]
        if answer_nodes:
            _, config, _ = await _node_config(session, answer_nodes[-1])
            answer, answer_metadata, event = await _answer(session, query, passages, answer_nodes[-1], config, langfuse_parent=lf_ctx.trace)
            run.answer = answer
            run.answer_metadata = answer_metadata
            trace_events.append(event)
        run.status = "completed"
        run.final_passages = [passage.to_dict() for passage in passages]
        run.trace_events = trace_events
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        run.error = None
        run.langfuse_trace_id = end_rag_trace(
            lf_ctx,
            output={
                "answer": run.answer[:2000] if run.answer else None,
                "passage_count": len(passages),
                "top_passages": _passage_preview(passages),
            },
            status_message="completed",
            metadata={
                "latency_ms": run.latency_ms,
                "passage_count": len(passages),
                "source_chunk_ids": [passage.chunk_id for passage in passages[:20]],
            },
        )
    except Exception as exc:
        logger.exception("RAG flow run failed: flow_id=%s run_id=%s", flow.flow_id, run.run_id)
        run.status = "failed"
        run.answer = None
        run.answer_metadata = {}
        run.final_passages = []
        run.trace_events = trace_events
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        run.error = _error_text(exc)
        run.langfuse_trace_id = end_rag_trace(
            lf_ctx, status_message="failed", metadata={"error": run.error},
        )
    await session.commit()
    await session.refresh(run)
    return RagFlowRunOut.model_validate(run, from_attributes=True)


async def get_rag_flow_run(session: AsyncSession, run_id: str) -> RagFlowRunOut:
    run = await session.get(RagFlowRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG flow run not found")
    return RagFlowRunOut.model_validate(run, from_attributes=True)


async def list_rag_flow_runs(
    session: AsyncSession,
    flow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RagFlowRunSummaryOut]:
    stmt = select(RagFlowRun).order_by(RagFlowRun.created_at.desc())
    if flow_id:
        stmt = stmt.where(RagFlowRun.flow_id == flow_id)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.scalars(stmt)).all()
    return [RagFlowRunSummaryOut.model_validate(row, from_attributes=True) for row in rows]


async def delete_rag_flow_run(session: AsyncSession, run_id: str) -> None:
    run = await session.get(RagFlowRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG flow run not found")
    await session.delete(run)
    await session.commit()
