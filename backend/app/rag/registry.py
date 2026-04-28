from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field


CONFIGURABLE_NODE_TYPES = {"passage_reranker", "passage_filter", "passage_compressor"}


@dataclass(frozen=True)
class ComponentAvailability:
    status: str
    reason: str


@dataclass(frozen=True)
class RagComponentSpec:
    node_type: str
    module_type: str
    display_name: str
    description: str
    capabilities: tuple[str, ...]
    config_schema: dict = field(default_factory=dict)
    secret_config_schema: dict = field(default_factory=dict)
    default_config: dict = field(default_factory=dict)
    source: str = "autorag"
    executable: bool = True
    requires_config: bool = False
    required_dependencies: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    requires_llm: bool = False
    requires_embedding: bool = False
    requires_api_key: bool = False
    optional_dependency_extra: str | None = None

    def availability(self, config: dict | None = None, has_secret: bool = False) -> ComponentAvailability:
        if self.required_env_vars and not has_secret:
            missing_env = [name for name in self.required_env_vars if not os.getenv(name)]
            if missing_env:
                return ComponentAvailability("missing_env", f"Missing environment variables: {', '.join(missing_env)}")
        missing_deps = []
        for dependency in self.required_dependencies:
            try:
                found = importlib.util.find_spec(dependency) is not None
            except ModuleNotFoundError:
                found = False
            if not found:
                missing_deps.append(dependency)
        if missing_deps:
            return ComponentAvailability("missing_dependency", f"Missing Python dependencies: {', '.join(missing_deps)}")
        if self.requires_api_key and not has_secret:
            return ComponentAvailability("needs_config", "API key is required.")
        if self.requires_llm and not ((config or {}).get("model_id") or (config or {}).get("agent_id")):
            return ComponentAvailability("needs_config", "LLM model_id or agent_id is required.")
        if self.requires_embedding and not (config or {}).get("embedding_model_id"):
            return ComponentAvailability("needs_config", "Embedding model_id is required.")
        if self.requires_config:
            required = self.config_schema.get("required", [])
            missing = [key for key in required if (config or {}).get(key) in (None, "")]
            if missing:
                return ComponentAvailability("needs_config", f"Missing config: {', '.join(missing)}")
        if not self.executable:
            return ComponentAvailability("adapter_only", "Registered for configuration; executable adapter is pending.")
        return ComponentAvailability("available", "Available")


class RagComponentRegistry:
    def __init__(self) -> None:
        self._components: dict[tuple[str, str], RagComponentSpec] = {}

    def register(self, spec: RagComponentSpec) -> None:
        self._components[(spec.node_type, spec.module_type)] = spec

    def get(self, node_type: str, module_type: str) -> RagComponentSpec | None:
        return self._components.get((node_type, module_type))

    def list(self, node_type: str | None = None) -> list[RagComponentSpec]:
        items = list(self._components.values())
        if node_type:
            items = [item for item in items if item.node_type == node_type]
        return sorted(items, key=lambda item: (item.node_type, item.display_name))


def schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


rag_component_registry = RagComponentRegistry()

for name, display, properties, defaults in [
    (
        "bm25",
        "BM25",
        {
            "top_k": {"type": "integer", "title": "Top K", "minimum": 1},
            "bm25_tokenizer": {"type": "string", "title": "BM25 Tokenizer", "enum": ["simple", "space"]},
        },
        {"top_k": 5, "bm25_tokenizer": "simple"},
    ),
    (
        "vectordb",
        "VectorDB",
        {"top_k": {"type": "integer", "title": "Top K", "minimum": 1}},
        {"top_k": 5},
    ),
    (
        "hybrid_rrf",
        "Hybrid RRF",
        {
            "top_k": {
                "type": "integer",
                "title": "Final Top K",
                "minimum": 1,
                "description": "融合排序后最终返回的 chunk 数量。",
            },
            "bm25_top_k": {
                "type": "integer",
                "title": "BM25 Candidate Top K",
                "minimum": 1,
                "description": "每个 query 从 BM25 召回的候选 chunk 数量，留空则使用 Final Top K。",
            },
            "vectordb_top_k": {
                "type": "integer",
                "title": "VectorDB Candidate Top K",
                "minimum": 1,
                "description": "每个 query 从 VectorDB 召回的候选 chunk 数量，留空则使用 Final Top K。",
            },
            "bm25_tokenizer": {"type": "string", "title": "BM25 Tokenizer", "enum": ["simple", "space"]},
            "lexical_weight": {"type": "number", "title": "Lexical Weight", "minimum": 0},
            "semantic_weight": {"type": "number", "title": "Semantic Weight", "minimum": 0},
            "rrf_k": {"type": "number", "title": "RRF K", "minimum": 1},
        },
        {
            "top_k": 5,
            "bm25_top_k": 10,
            "vectordb_top_k": 10,
            "bm25_tokenizer": "simple",
            "lexical_weight": 1.0,
            "semantic_weight": 1.0,
            "rrf_k": 60,
        },
    ),
    (
        "hybrid_cc",
        "Hybrid CC",
        {
            "top_k": {
                "type": "integer",
                "title": "Final Top K",
                "minimum": 1,
                "description": "融合排序后最终返回的 chunk 数量。",
            },
            "bm25_top_k": {
                "type": "integer",
                "title": "BM25 Candidate Top K",
                "minimum": 1,
                "description": "每个 query 从 BM25 召回的候选 chunk 数量，留空则使用 Final Top K。",
            },
            "vectordb_top_k": {
                "type": "integer",
                "title": "VectorDB Candidate Top K",
                "minimum": 1,
                "description": "每个 query 从 VectorDB 召回的候选 chunk 数量，留空则使用 Final Top K。",
            },
            "bm25_tokenizer": {"type": "string", "title": "BM25 Tokenizer", "enum": ["simple", "space"]},
            "lexical_weight": {"type": "number", "title": "Lexical Weight", "minimum": 0},
            "semantic_weight": {"type": "number", "title": "Semantic Weight", "minimum": 0},
            "normalize_method": {"type": "string", "title": "Normalize Method", "enum": ["mm", "tmm", "z", "dbsf"]},
        },
        {
            "top_k": 5,
            "bm25_top_k": 10,
            "vectordb_top_k": 10,
            "bm25_tokenizer": "simple",
            "lexical_weight": 0.5,
            "semantic_weight": 0.5,
            "normalize_method": "mm",
        },
    ),
]:
    rag_component_registry.register(
        RagComponentSpec(
            node_type="retrieval",
            module_type=name,
            display_name=display,
            description=f"AutoRAG retrieval module: {display}.",
            capabilities=("retrieval", "autorag"),
            config_schema=schema(properties),
            default_config=defaults,
        )
    )

for name, display, requires_llm in [
    ("pass_query_expansion", "Pass Query Expansion", False),
    ("query_decompose", "Query Decompose", True),
    ("hyde", "HyDE", True),
    ("multi_query_expansion", "Multi Query Expansion", True),
]:
    rag_component_registry.register(
        RagComponentSpec(
            node_type="query_expansion",
            module_type=name,
            display_name=display,
            description=f"AutoRAG query expansion module: {display}.",
            capabilities=("query_expansion", "pre_retrieval", "autorag"),
            config_schema=schema(
                {
                    "model_id": {"type": "string", "title": "LLM 模型"},
                    "agent_id": {"type": "string", "title": "Agent Profile"},
                    "temperature": {"type": "number", "title": "Temperature", "minimum": 0, "maximum": 2},
                    "max_output_tokens": {
                        "type": "integer",
                        "title": "Max output tokens",
                        "minimum": 64,
                        "maximum": 32768,
                        "description": "Query Expansion 输出预算，默认 512，避免扩展 query 被过早截断。",
                    },
                }
            ),
            default_config={"temperature": 0, "max_output_tokens": 512} if requires_llm else {},
            requires_llm=requires_llm,
        )
    )

rag_component_registry.register(
    RagComponentSpec(
        node_type="passage_augmenter",
        module_type="pass_passage_augmenter",
        display_name="Pass Passage Augmenter",
        description="AutoRAG pass-through augmenter.",
        capabilities=("passage_augmenter", "autorag"),
    )
)
rag_component_registry.register(
    RagComponentSpec(
        node_type="passage_augmenter",
        module_type="prev_next_augmenter",
        display_name="Prev Next Augmenter",
        description="Add previous and/or next chunks around retrieved passages.",
        capabilities=("passage_augmenter", "context_window", "autorag"),
        config_schema=schema(
            {
                "previous_chunks": {"type": "integer", "minimum": 0},
                "next_chunks": {"type": "integer", "minimum": 0},
                "same_document_only": {"type": "boolean"},
                "top_k": {"type": "integer", "minimum": 1},
            }
        ),
        default_config={"previous_chunks": 1, "next_chunks": 1, "same_document_only": True},
    )
)

for name in [
    "pass_reranker",
    "time_reranker",
]:
    rag_component_registry.register(
        RagComponentSpec(
            node_type="passage_reranker",
            module_type=name,
            display_name=name.replace("_", " ").title(),
            description=f"AutoRAG reranker module: {name}.",
            capabilities=("passage_reranker", "autorag"),
            config_schema=schema({"top_k": {"type": "integer", "minimum": 1}}),
            default_config={"top_k": 5},
        )
    )

for name, env_name, default_model in [
    ("cohere_reranker", "COHERE_API_KEY", "rerank-v3.5"),
    ("voyageai_reranker", "VOYAGE_API_KEY", "rerank-2"),
    ("jina_reranker", "JINA_API_KEY", "jina-reranker-v2-base-multilingual"),
    ("mixedbread_ai_reranker", "MXBAI_API_KEY", "mixedbread-ai/mxbai-rerank-large-v1"),
]:
    rag_component_registry.register(
        RagComponentSpec(
            node_type="passage_reranker",
            module_type=name,
            display_name=name.replace("_", " ").title(),
            description=f"API-backed AutoRAG reranker module: {name}.",
            capabilities=("passage_reranker", "api", "autorag"),
            config_schema=schema(
                {
                    "model": {"type": "string", "title": "模型名称"},
                    "top_k": {"type": "integer", "title": "Top K", "minimum": 1},
                    "batch": {"type": "integer", "title": "Batch size", "minimum": 1},
                }
            ),
            secret_config_schema=schema(
                {"api_key": {"type": "string", "title": "API Key", "secret": True}},
                required=["api_key"],
            ),
            default_config={"model": default_model, "top_k": 5},
            required_env_vars=(),
            requires_api_key=True,
        )
    )

rag_component_registry.register(
    RagComponentSpec(
        node_type="passage_reranker",
        module_type="rankgpt",
        display_name="RankGPT",
        description="LLM-based passage reranking.",
        capabilities=("passage_reranker", "llm", "autorag"),
        config_schema=schema(
            {
                "model_id": {"type": "string", "title": "LLM 模型"},
                "agent_id": {"type": "string", "title": "Agent Profile"},
                "top_k": {"type": "integer", "title": "Top K", "minimum": 1},
                "temperature": {"type": "number", "title": "Temperature", "minimum": 0, "maximum": 2},
            }
        ),
        default_config={"top_k": 5, "temperature": 0},
        requires_llm=True,
    )
)

for name, dependency in [
    ("upr", None),
    ("tart", None),
    ("monot5", "transformers"),
    ("ko_reranker", None),
    ("colbert_reranker", None),
    ("sentence_transformer_reranker", "sentence_transformers"),
    ("flag_embedding_reranker", "FlagEmbedding"),
    ("flag_embedding_llm_reranker", "FlagEmbedding"),
    ("openvino_reranker", "openvino"),
    ("flashrank_reranker", "flashrank"),
]:
        extra = {
            "monot5": "rag-rerank-local",
            "sentence_transformer_reranker": "rag-rerank-local",
            "flashrank_reranker": "rag-rerank-local",
            "flag_embedding_reranker": "rag-rerank-flag",
            "flag_embedding_llm_reranker": "rag-rerank-flag",
            "openvino_reranker": "rag-rerank-openvino",
        }.get(name)
        rag_component_registry.register(
        RagComponentSpec(
            node_type="passage_reranker",
            module_type=name,
            display_name=name.replace("_", " ").title(),
            description=f"Heavy/local AutoRAG reranker module: {name}.",
            capabilities=("passage_reranker", "local_model", "autorag"),
            config_schema=schema({"model_name": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1}}),
            default_config={"top_k": 5},
            required_dependencies=(dependency,) if dependency else (),
            executable=False,
            optional_dependency_extra=extra,
        )
    )

for name in ["pass_passage_filter", "similarity_threshold_cutoff", "similarity_percentile_cutoff", "recency_filter", "threshold_cutoff", "percentile_cutoff"]:
    defaults = {}
    properties = {}
    required: list[str] = []
    if "threshold" in name or name == "threshold_cutoff":
        properties["threshold"] = {"type": "number"}
        defaults["threshold"] = 0.5
    if "percentile" in name:
        properties["percentile"] = {"type": "number", "minimum": 0, "maximum": 100}
        defaults["percentile"] = 50
    if name == "recency_filter":
        properties["threshold_datetime"] = {"type": "string"}
        properties["metadata_field"] = {"type": "string"}
        defaults = {"threshold_datetime": "", "metadata_field": "last_modified_datetime"}
        required = ["threshold_datetime"]
    rag_component_registry.register(
        RagComponentSpec(
            node_type="passage_filter",
            module_type=name,
            display_name=name.replace("_", " ").title(),
            description=f"AutoRAG passage filter module: {name}.",
            capabilities=("passage_filter", "autorag"),
            config_schema=schema(properties, required=required),
            default_config=defaults,
            requires_config=bool(required),
        )
    )

for name, display, requires_llm, executable in [
    ("pass_compressor", "Pass Compressor", False, True),
    ("tree_summarize", "Tree Summarize", True, True),
    ("refine", "Refine", True, True),
    ("longllmlingua", "LongLLMLingua", False, False),
]:
    rag_component_registry.register(
        RagComponentSpec(
            node_type="passage_compressor",
            module_type=name,
            display_name=display,
            description=f"AutoRAG passage compressor module: {display}.",
            capabilities=("passage_compressor", "autorag"),
            config_schema=schema(
                {
                    "model_id": {"type": "string", "title": "LLM 模型"},
                    "agent_id": {"type": "string", "title": "Agent Profile"},
                    "max_output_tokens": {
                        "type": "integer",
                        "title": "Max output tokens",
                        "minimum": 64,
                        "maximum": 32768,
                        "description": "Compressor 输出预算，默认 1024，保留压缩后的事实密度。",
                    },
                    "target_chars": {"type": "integer", "title": "目标字符数", "minimum": 100},
                }
            ),
            default_config={"max_output_tokens": 1024, "target_chars": 700} if requires_llm else {},
            requires_llm=requires_llm,
            executable=executable,
            required_dependencies=("llmlingua",) if name == "longllmlingua" else (),
            optional_dependency_extra="rag-compress" if name == "longllmlingua" else None,
        )
    )

rag_component_registry.register(
    RagComponentSpec(
        node_type="answer_generator",
        module_type="llm_answer",
        display_name="LLM Answer",
        description="Generate the final answer from retrieved passages.",
        capabilities=("answer_generation", "llm", "ragas"),
        config_schema=schema(
            {
                "model_id": {"type": "string", "title": "LLM 模型"},
                "agent_id": {"type": "string", "title": "Agent Profile"},
                "temperature": {"type": "number", "title": "Temperature", "minimum": 0, "maximum": 2},
                "max_output_tokens": {"type": "integer", "title": "Max output tokens", "minimum": 64, "maximum": 32768},
                "system_prompt": {"type": "string", "title": "System Prompt"},
            }
        ),
        default_config={
            "temperature": 0,
            "max_output_tokens": 1024,
            "system_prompt": "请仅基于给定上下文回答问题。若上下文不足，请明确说明无法从材料中确定。",
        },
        requires_llm=True,
    )
)
