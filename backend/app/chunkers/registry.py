from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkerAvailability:
    status: str
    reason: str


@dataclass(frozen=True)
class ChunkerStrategySpec:
    chunker_name: str
    display_name: str
    description: str
    module_type: str
    chunk_method: str
    capabilities: tuple[str, ...]
    config_schema: dict = field(default_factory=dict)
    default_config: dict = field(default_factory=dict)
    source: str = "autorag"
    enabled: bool = True
    required_dependencies: tuple[str, ...] = ()
    requires_embedding_model: bool = False
    executable: bool = True

    def availability(self) -> ChunkerAvailability:
        if not self.enabled:
            return ChunkerAvailability("disabled", "Chunker is disabled.")
        if not self.executable:
            return ChunkerAvailability("adapter_only", "Registered for configuration; executable adapter is pending.")
        missing_deps = []
        for dependency in self.required_dependencies:
            try:
                found = importlib.util.find_spec(dependency) is not None
            except ModuleNotFoundError:
                found = False
            if not found:
                missing_deps.append(dependency)
        if missing_deps:
            return ChunkerAvailability("missing_dependency", f"Missing Python dependencies: {', '.join(missing_deps)}")
        if self.requires_embedding_model:
            return ChunkerAvailability("needs_config", "Requires embedding_model_id in chunker_config.")
        return ChunkerAvailability("available", "Available")


class ChunkerRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, ChunkerStrategySpec] = {}

    def register(self, strategy: ChunkerStrategySpec) -> None:
        self._strategies[strategy.chunker_name] = strategy

    def get(self, chunker_name: str) -> ChunkerStrategySpec | None:
        return self._strategies.get(chunker_name)

    def list_enabled(self) -> list[ChunkerStrategySpec]:
        return sorted(
            [strategy for strategy in self._strategies.values() if strategy.enabled],
            key=lambda strategy: (strategy.module_type, strategy.display_name),
        )


def schema(properties: dict, required: list[str] | None = None) -> dict:
    common = {
        "chunk_size": {"type": "integer", "minimum": 1},
        "overlap_enabled": {"type": "boolean"},
        "chunk_overlap": {"type": "integer", "minimum": 0},
        "chunk_overlap_ratio": {"type": "number", "minimum": 0, "maximum": 0.9},
        "overlap_strategy": {"type": "string", "enum": ["chars", "tokens", "sentences"]},
        "include_metadata": {"type": "boolean"},
        "metadata_template": {"type": "string"},
        "add_file_name": {"type": "string", "enum": ["none", "en", "english", "ko", "korean", "ja", "japanese"]},
    }
    return {"type": "object", "properties": common | properties, "required": required or []}


BASE_DEFAULT = {
    "chunk_size": 512,
    "overlap_enabled": True,
    "chunk_overlap": 64,
    "chunk_overlap_ratio": 0,
    "overlap_strategy": "chars",
    "include_metadata": True,
    "metadata_template": "",
    "add_file_name": "none",
}

chunker_registry = ChunkerRegistry()

for name, display, method, capabilities, default_update in [
    ("langchain_token", "LangChain / Token", "Token", ("token", "autorag", "langchain_chunk"), {"overlap_strategy": "tokens"}),
    ("langchain_recursive_character", "LangChain / Recursive Character", "RecursiveCharacter", ("character", "recursive", "autorag", "langchain_chunk"), {}),
    ("langchain_character", "LangChain / Character", "Character", ("character", "autorag", "langchain_chunk"), {}),
]:
    chunker_registry.register(
        ChunkerStrategySpec(
            chunker_name=name,
            display_name=display,
            description=f"AutoRAG LangChain chunk method: {method}. Local adapter is available.",
            module_type="langchain_chunk",
            chunk_method=method,
            capabilities=capabilities,
            config_schema=schema({}),
            default_config=BASE_DEFAULT | default_update,
        )
    )

chunker_registry.register(
    ChunkerStrategySpec(
        chunker_name="langchain_konlpy",
        display_name="LangChain / KoNLPy",
        description="AutoRAG LangChain sentence chunk method for Korean. Requires KoNLPy.",
        module_type="langchain_chunk",
        chunk_method="konlpy",
        capabilities=("sentence", "korean", "autorag", "langchain_chunk"),
        config_schema=schema({"sentence_overlap": {"type": "integer", "minimum": 0}}),
        default_config=BASE_DEFAULT | {"overlap_strategy": "sentences", "sentence_overlap": 1},
        required_dependencies=("konlpy",),
    )
)

for name, display, method, capabilities, default_update in [
    ("llama_index_token", "LlamaIndex / Token", "Token", ("token", "autorag", "llama_index_chunk"), {"overlap_strategy": "tokens"}),
    ("llama_index_sentence", "LlamaIndex / Sentence", "Sentence", ("sentence", "autorag", "llama_index_chunk"), {"overlap_strategy": "sentences"}),
    ("llama_index_sentence_window", "LlamaIndex / Sentence Window", "SentenceWindow", ("sentence", "window", "autorag", "llama_index_chunk"), {"window_size": 3, "overlap_strategy": "sentences"}),
    ("llama_index_simple", "LlamaIndex / Simple", "Simple", ("simple", "autorag", "llama_index_chunk"), {"chunk_size": 100000, "overlap_enabled": False}),
]:
    chunker_registry.register(
        ChunkerStrategySpec(
            chunker_name=name,
            display_name=display,
            description=f"AutoRAG LlamaIndex chunk method: {method}. Local adapter is available.",
            module_type="llama_index_chunk",
            chunk_method=method,
            capabilities=capabilities,
            config_schema=schema({"window_size": {"type": "integer", "minimum": 1}} if "window" in capabilities else {}),
            default_config=BASE_DEFAULT | default_update,
        )
    )

for name, display, method in [
    ("llama_index_semantic", "LlamaIndex / Semantic", "Semantic_llama_index"),
    ("llama_index_semantic_doubling", "LlamaIndex / Semantic Doubling", "SemanticDoubling"),
]:
    chunker_registry.register(
        ChunkerStrategySpec(
            chunker_name=name,
            display_name=display,
            description=f"AutoRAG LlamaIndex semantic chunk method: {method}. Requires embedding_model_id.",
            module_type="llama_index_chunk",
            chunk_method=method,
            capabilities=("semantic", "embedding", "autorag", "llama_index_chunk"),
            config_schema=schema({"embedding_model_id": {"type": "string"}}, required=["embedding_model_id"]),
            default_config=BASE_DEFAULT | {"embedding_model_id": "", "overlap_strategy": "sentences"},
            requires_embedding_model=True,
        )
    )
